import os
import re
import json
import socket
import subprocess
import concurrent.futures
from urllib.parse import urlparse

INPUT_FILE = "outreach_contacts.json"
OUTPUT_FILE = "outreach_contacts_verified.json"
MARKDOWN_REPORT = "outreach_contacts_verified.md"

def load_contacts():
    if os.path.exists(INPUT_FILE):
        try:
            with open(INPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {INPUT_FILE}: {e}")
            return {}
    return {}

def check_domain_resolution(domain):
    try:
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False

def check_mx_record(domain):
    try:
        result = subprocess.run(
            ["nslookup", "-type=mx", domain],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout
        return "mail exchanger" in output or "MX" in output or "preference" in output
    except Exception:
        return False

def verify_email(email):
    # Syntax check
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid syntax"
        
    domain = email.split('@')[1]
    
    # Domain resolution check
    if not check_domain_resolution(domain):
        return False, "Domain does not resolve (inactive website)"
        
    # MX record check
    if not check_mx_record(domain):
        return False, "No active MX records (cannot receive mail)"
        
    return True, "Valid"

def process_creator(url, creator_data):
    emails = creator_data.get("emails", [])
    verified_emails = []
    invalid_emails = []
    
    for email in emails:
        is_valid, reason = verify_email(email)
        if is_valid:
            verified_emails.append(email)
        else:
            invalid_emails.append({"email": email, "reason": reason})
            
    # Copy creator data and update emails
    updated_data = creator_data.copy()
    updated_data["verified_emails"] = verified_emails
    updated_data["invalid_emails"] = invalid_emails
    
    return url, updated_data

def main():
    contacts = load_contacts()
    if not contacts:
        print("No contacts found to verify. Make sure outreach_contacts.json exists and is populated.")
        return
        
    print(f"Loaded {len(contacts)} creators from {INPUT_FILE}...")
    print("Verifying email domains and MX records concurrently...")
    
    verified_contacts = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {
            executor.submit(process_creator, url, data): url
            for url, data in contacts.items()
        }
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                url, updated_data = future.result()
                verified_contacts[url] = updated_data
            except Exception as e:
                print(f"Error processing {url}: {e}")
                
    # Save the verified JSON file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(verified_contacts, f, indent=2, ensure_ascii=False)
        
    # Write verified markdown report
    with open(MARKDOWN_REPORT, "w", encoding="utf-8") as f:
        f.write("# Verified Creator Outreach List\n\n")
        f.write("This directory contains email validation status and active outreach profiles for your creator target queue. Emails are validated via DNS resolution and MX record checks.\n\n")
        
        # Summary
        total = len(verified_contacts)
        total_with_verified_emails = sum(1 for c in verified_contacts.values() if c.get("verified_emails"))
        total_with_socials = sum(1 for c in verified_contacts.values() if any(c.get("socials", {}).values()))
        
        f.write("## Outreach Summary\n")
        f.write(f"- **Total Creators In Queue**: {total}\n")
        f.write(f"- **Creators with Verified Deliverable Emails**: {total_with_verified_emails} ({total_with_verified_emails/total*100:.1f}%)\n")
        f.write(f"- **Creators reachable via Social Media (IG/X/LinkedIn)**: {total_with_socials} ({total_with_socials/total*100:.1f}%)\n\n")
        
        f.write("## Outreach Channels Directory\n\n")
        f.write("| Profile | Channel | Verified Emails | Best Social Reach | Websites / Links | Video Link |\n")
        f.write("|---------|---------|-----------------|-------------------|------------------|------------|\n")
        
        for url, r in sorted(verified_contacts.items(), key=lambda x: x[1]['profile']):
            profile = r.get("profile", "")
            channel_name = r.get("channel_name", "")
            
            verified_emails = ", ".join(r.get("verified_emails", [])) or "*No verified email found*"
            
            socials = r.get("socials", {})
            reach_channels = []
            if socials.get("linkedin"):
                reach_channels.append(f"[LinkedIn]({socials.get('linkedin')})")
            if socials.get("instagram"):
                reach_channels.append(f"[Instagram]({socials.get('instagram')})")
            if socials.get("twitter"):
                reach_channels.append(f"[X/Twitter]({socials.get('twitter')})")
            social_col = ", ".join(reach_channels) if reach_channels else "None found"
            
            web_links = []
            if socials.get('linktree'):
                web_links.append(f"[Linktree]({socials.get('linktree')})")
            for web in r.get("websites", [])[:2]:
                domain = urlparse(web).netloc
                web_links.append(f"[{domain}]({web})")
            web_col = ", ".join(web_links) if web_links else "-"
            
            f.write(f"| **{profile}** | {channel_name} | {verified_emails} | {social_col} | {web_col} | [Watch]({url}) |\n")
            
        # Detail invalid emails
        f.write("\n## Blocked / Invalid Emails (Skipped)\n\n")
        f.write("The following emails were automatically detected as inactive/undeliverable to prevent bounces and domain reputation damage:\n\n")
        f.write("| Profile | Extracted Email | Reason for Failure |\n")
        f.write("|---------|-----------------|--------------------|\n")
        
        has_invalid = False
        for url, r in verified_contacts.items():
            for invalid in r.get("invalid_emails", []):
                f.write(f"| {r['profile']} | `{invalid['email']}` | {invalid['reason']} |\n")
                has_invalid = True
                
        if not has_invalid:
            f.write("| None | - | - |\n")
            
        f.write("\n\n*Outreach list verified dynamically by Antigravity verification engine.*")
        
    print(f"Verification complete! Saved JSON to {OUTPUT_FILE} and Markdown to {MARKDOWN_REPORT}.")

if __name__ == "__main__":
    main()

// State management
let leads = {};
let tracker = {};
let selectedUrl = null;

// DOM Elements
const leadsList = document.getElementById('leads-list');
const searchInput = document.getElementById('search-input');
const filterSelect = document.getElementById('filter-select');
const sortSelect = document.getElementById('sort-select');
const welcomeView = document.getElementById('welcome-view');
const detailsView = document.getElementById('details-view');

// Details elements
const creatorChannelName = document.getElementById('creator-channel-name');
const creatorProfileId = document.getElementById('creator-profile-id');
const contactedCheckbox = document.getElementById('contacted-checkbox');
const videoLink = document.getElementById('video-link');
const channelLink = document.getElementById('channel-link');
const emailsContainer = document.getElementById('emails-container');
const socialsContainer = document.getElementById('socials-container');
const websitesContainer = document.getElementById('websites-container');
const mailtoBtn = document.getElementById('mailto-btn');

// Tracking elements
const outreachChannelSelect = document.getElementById('outreach-channel-select');
const contactNotes = document.getElementById('contact-notes');
const saveTrackerBtn = document.getElementById('save-tracker-btn');
const saveStatus = document.getElementById('save-status');

// AI Planner elements
const generateStrategyBtn = document.getElementById('generate-strategy-btn');
const aiLoading = document.getElementById('ai-loading');
const aiResult = document.getElementById('ai-result');
const aiEmpty = document.getElementById('ai-empty');
const aiOutreachAngle = document.getElementById('ai-outreach-angle');
const aiPitchScript = document.getElementById('ai-pitch-script');
const aiNextSteps = document.getElementById('ai-next-steps');
const copyScriptBtn = document.getElementById('copy-script-btn');

// Metrics elements
const metricTotal = document.getElementById('metric-total');
const metricContacted = document.getElementById('metric-contacted');
const metricPending = document.getElementById('metric-pending');
const metricRate = document.getElementById('metric-rate');

// Initial Load
document.addEventListener('DOMContentLoaded', async () => {
    await loadData();
    setupEventListeners();
});

async function loadData() {
    try {
        // Fetch verified contacts
        const contactsRes = await fetch('/api/contacts');
        if (contactsRes.ok) {
            leads = await contactsRes.json();
        } else {
            console.error('Failed to load contacts');
            leadsList.innerHTML = `<div class="lead-loading" style="color: var(--accent-red)">Failed to load contacts list. Ensure finder has run.</div>`;
            return;
        }

        // Fetch tracker progress
        const trackerRes = await fetch('/api/tracker');
        if (trackerRes.ok) {
            tracker = await trackerRes.json();
        }

        renderLeadsList();
        renderMetrics();
    } catch (err) {
        console.error('Error fetching data:', err);
        leadsList.innerHTML = `<div class="lead-loading" style="color: var(--accent-red)">Server connection error. Is server.py running?</div>`;
    }
}

function setupEventListeners() {
    // Search, filter, and sort listeners
    searchInput.addEventListener('input', () => renderLeadsList());
    filterSelect.addEventListener('change', () => renderLeadsList());
    sortSelect.addEventListener('change', () => renderLeadsList());

    // Save notes button
    saveTrackerBtn.addEventListener('click', saveLeadTracking);

    // Checkbox auto-save
    contactedCheckbox.addEventListener('change', () => {
        saveLeadTracking(false); // auto-save without showing manual "Saved" status
    });

    // Generate strategy button
    generateStrategyBtn.addEventListener('click', generateStrategy);

    // Copy script button
    copyScriptBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(aiPitchScript.textContent);
        const originalText = copyScriptBtn.innerHTML;
        copyScriptBtn.innerHTML = `<i data-lucide="check" class="text-accent-green"></i> Copied!`;
        lucide.createIcons();
        setTimeout(() => {
            copyScriptBtn.innerHTML = originalText;
            lucide.createIcons();
        }, 2000);
    });

    // Mailto button
    if (mailtoBtn) {
        mailtoBtn.addEventListener('click', () => {
            if (!selectedUrl) return;
            const lead = leads[selectedUrl];
            
            let email = "";
            if (lead.verified_emails && lead.verified_emails.length > 0) {
                email = lead.verified_emails[0];
            } else {
                alert("No verified email found for this creator. Please copy the script instead.");
                return;
            }

            const body = aiPitchScript.textContent || "";
            let subject = `Partnership Inquiry: Scaling ${lead.channel_name || 'your channel'}`;
            
            const lines = body.split('\n');
            if (lines.length > 0 && lines[0].toLowerCase().includes('subject:')) {
                subject = lines[0].replace(/subject:/i, '').replace(/"/g, '').trim();
            }

            const mailtoLink = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
            window.location.href = mailtoLink;
        });
    }
}

function renderMetrics() {
    const urls = Object.keys(leads);
    const totalCount = urls.length;
    
    let contactedCount = 0;
    urls.forEach(url => {
        if (tracker[url] && tracker[url].contacted) {
            contactedCount++;
        }
    });

    const pendingCount = totalCount - contactedCount;
    const rate = totalCount > 0 ? Math.round((contactedCount / totalCount) * 100) : 0;

    metricTotal.textContent = totalCount;
    metricContacted.textContent = contactedCount;
    metricPending.textContent = pendingCount;
    metricRate.textContent = `${rate}%`;
}

function renderLeadsList() {
    leadsList.innerHTML = '';
    
    const filterQuery = searchInput.value.toLowerCase();
    const filterStatus = filterSelect.value;
    const sortMode = sortSelect.value;

    let sortedUrls = Object.keys(leads);

    // Filter
    sortedUrls = sortedUrls.filter(url => {
        const lead = leads[url];
        const profile = lead.profile.toLowerCase();
        const channelName = (lead.channel_name || profile).toLowerCase();
        
        // Search Filter
        if (filterQuery && !profile.includes(filterQuery) && !channelName.includes(filterQuery)) {
            return false;
        }

        // Status Filter
        const isContacted = tracker[url] && tracker[url].contacted;
        let isFollowUpDue = false;
        if (tracker[url] && tracker[url].follow_up_date) {
            const followUpTime = new Date(tracker[url].follow_up_date).getTime();
            if (Date.now() >= followUpTime) isFollowUpDue = true;
        }

        if (filterStatus === 'pending' && isContacted) return false;
        if (filterStatus === 'contacted' && !isContacted) return false;
        if (filterStatus === 'followup' && !isFollowUpDue) return false;

        return true;
    });

    // Sort
    sortedUrls.sort((a, b) => {
        if (sortMode === 'alpha') {
            return leads[a].profile.localeCompare(leads[b].profile);
        } else if (sortMode === 'alpha-desc') {
            return leads[b].profile.localeCompare(leads[a].profile);
        } else if (sortMode === 'newest') {
            // Implicit newest based on index in Object.keys
            const allKeys = Object.keys(leads);
            return allKeys.indexOf(b) - allKeys.indexOf(a);
        } else if (sortMode === 'oldest') {
            const allKeys = Object.keys(leads);
            return allKeys.indexOf(a) - allKeys.indexOf(b);
        } else if (sortMode === 'followup') {
            const dateA = tracker[a]?.follow_up_date ? new Date(tracker[a].follow_up_date).getTime() : Infinity;
            const dateB = tracker[b]?.follow_up_date ? new Date(tracker[b].follow_up_date).getTime() : Infinity;
            return dateA - dateB;
        }
        return 0;
    });

    let renderedCount = 0;
    sortedUrls.forEach(url => {
        const lead = leads[url];
        const profile = lead.profile;
        const channelName = lead.channel_name || profile;
        const isContacted = tracker[url] && tracker[url].contacted;

        renderedCount++;

        let badgeHtml = '';
        if (tracker[url] && tracker[url].follow_up_date) {
            const followUpTime = new Date(tracker[url].follow_up_date).getTime();
            if (Date.now() >= followUpTime) {
                badgeHtml = '<i data-lucide="bell-ring" class="text-accent-red" style="width: 14px; height: 14px; margin-left: 6px;"></i>';
            }
        }

        const leadItem = document.createElement('div');
        leadItem.className = `lead-item ${selectedUrl === url ? 'active' : ''}`;
        leadItem.innerHTML = `
            <div class="lead-info">
                <span class="lead-name">${channelName}${badgeHtml}</span>
                <span class="lead-subtext">${profile} • ${lead.target_platform}</span>
            </div>
            <div class="lead-status ${isContacted ? 'status-contacted' : 'status-pending'}"></div>
        `;

        leadItem.addEventListener('click', () => selectLead(url));
        leadsList.appendChild(leadItem);
    });

    if (renderedCount === 0) {
        leadsList.innerHTML = `<div class="lead-loading">No matching creators found.</div>`;
    }
    
    // Initialize Lucide icons on list items if any
    lucide.createIcons();
}

function selectLead(url) {
    selectedUrl = url;
    
    // Toggle active classes in list
    document.querySelectorAll('.lead-item').forEach((item, idx) => {
        const sortedUrls = Object.keys(leads).sort((a, b) => leads[a].profile.localeCompare(leads[b].profile));
        // Simple search query-proof index matching
    });
    // For simplicity, just re-render list
    renderLeadsList();

    const lead = leads[url];
    const track = tracker[url] || {};

    // Switch views
    welcomeView.classList.add('hidden');
    detailsView.classList.remove('hidden');

    // Populate profile details
    creatorChannelName.textContent = lead.channel_name || lead.profile;
    creatorProfileId.textContent = lead.channel_handle || `@${lead.profile}`;
    videoLink.href = lead.video_url;
    channelLink.href = lead.channel_url || '#';
    if (!lead.channel_url) {
        channelLink.classList.add('hidden');
    } else {
        channelLink.classList.remove('hidden');
    }

    // Populate Tracking status
    contactedCheckbox.checked = !!track.contacted;
    outreachChannelSelect.value = track.outreach_channel || '';
    contactNotes.value = track.notes || '';

    // Render Emails
    emailsContainer.innerHTML = '';
    const emails = lead.verified_emails || lead.emails || [];
    if (emails.length > 0) {
        emails.forEach(email => {
            const el = document.createElement('a');
            el.className = 'contact-badge contact-badge-email';
            el.href = `mailto:${email}`;
            el.innerHTML = `<i data-lucide="mail"></i> ${email}`;
            emailsContainer.appendChild(el);
        });
    } else {
        emailsContainer.innerHTML = '<span class="empty-text">No verified business emails found in descriptions.</span>';
    }

    // Render Social Handles
    socialsContainer.innerHTML = '';
    const socials = lead.socials || {};
    let hasSocials = false;

    const socialIcons = {
        instagram: 'instagram',
        twitter: 'twitter',
        linkedin: 'linkedin',
        tiktok: 'video',
        facebook: 'facebook',
        linktree: 'link',
        patreon: 'heart'
    };

    Object.keys(socials).forEach(plat => {
        const link = socials[plat];
        if (link) {
            hasSocials = true;
            const el = document.createElement('a');
            el.className = 'contact-badge contact-badge-social';
            el.href = link;
            el.target = '_blank';
            const iconName = socialIcons[plat] || 'globe';
            el.innerHTML = `<i data-lucide="${iconName}"></i> ${plat.charAt(0).toUpperCase() + plat.slice(1)}`;
            socialsContainer.appendChild(el);
        }
    });

    if (!hasSocials) {
        socialsContainer.innerHTML = '<span class="empty-text">No direct social profiles discovered.</span>';
    }

    // Render Websites
    websitesContainer.innerHTML = '';
    const websites = lead.websites || [];
    if (websites.length > 0) {
        websites.forEach(web => {
            const domain = new URL(web).hostname.replace('www.', '');
            const el = document.createElement('a');
            el.className = 'contact-badge';
            el.href = web;
            el.target = '_blank';
            el.innerHTML = `<i data-lucide="video"></i> ${domain}`;
            websitesContainer.appendChild(el);
        });
    } else {
        websitesContainer.innerHTML = '<span class="empty-text">No external websites listed.</span>';
    }

    // Calculate Best Way to Reach
    const bestReachMethod = document.getElementById('best-reach-method');
    const bestReachScore = document.getElementById('best-reach-score');
    
    let bestMethod = "Unknown";
    let score = 0;
    let icon = "help-circle";
    let colorClass = "";

    const verifiedEmails = lead.verified_emails || lead.emails || [];
    const soc = lead.socials || {};

    if (verifiedEmails.length > 0) {
        bestMethod = "Cold Email";
        score = 95;
        icon = "mail";
        colorClass = "text-accent-green";
    } else if (soc.instagram) {
        bestMethod = "Instagram DM";
        score = 85;
        icon = "instagram";
        colorClass = "text-accent-cyan";
    } else if (soc.twitter) {
        bestMethod = "Twitter DM";
        score = 75;
        icon = "twitter";
        colorClass = "text-accent-cyan";
    } else if (soc.linkedin) {
        bestMethod = "LinkedIn Msg";
        score = 70;
        icon = "linkedin";
        colorClass = "text-accent-purple";
    } else if (lead.websites && lead.websites.length > 0) {
        bestMethod = "Website Form";
        score = 50;
        icon = "globe";
        colorClass = "text-accent-purple";
    } else {
        bestMethod = "No Direct Channel";
        score = 10;
        icon = "alert-circle";
        colorClass = "text-accent-red";
    }

    bestReachMethod.innerHTML = `<i data-lucide="${icon}" class="${colorClass}"></i> ${bestMethod}`;
    bestReachScore.textContent = `${score}% Match`;
    bestReachScore.style.color = `var(--${colorClass.replace('text-', '')})`;
    bestReachScore.style.background = `rgba(${score > 80 ? '16, 185, 129' : score > 60 ? '6, 182, 212' : '239, 68, 68'}, 0.2)`;

    // Load custom AI Strategy from tracker database if it exists
    renderStrategy(track.custom_strategy);

    // Trigger Lucide to render icons for the detail view elements
    lucide.createIcons();
}

function renderStrategy(strategy) {
    if (strategy && (strategy.outreach_angle || strategy.pitch_script)) {
        if (aiEmpty) aiEmpty.classList.add('hidden');
        if (aiResult) aiResult.classList.remove('hidden');
        if (aiLoading) aiLoading.classList.add('hidden');
        generateStrategyBtn.disabled = false;

        aiOutreachAngle.textContent = strategy.outreach_angle || 'No angle generated.';
        aiPitchScript.textContent = strategy.pitch_script || 'No script generated.';
        
        aiNextSteps.innerHTML = '';
        const steps = strategy.next_steps || [];
        if (steps.length > 0) {
            steps.forEach(step => {
                const li = document.createElement('li');
                li.textContent = step;
                aiNextSteps.appendChild(li);
            });
        } else {
            aiNextSteps.innerHTML = '<li>Check social links and prepare outreach script.</li>';
        }
    } else {
        if (aiEmpty) aiEmpty.classList.remove('hidden');
        if (aiResult) aiResult.classList.add('hidden');
        if (aiLoading) aiLoading.classList.add('hidden');
        generateStrategyBtn.disabled = false;
    }
}

window.setFollowUp = function(hours) {
    if (!selectedUrl) return;
    const fDate = new Date(Date.now() + hours * 60 * 60 * 1000);
    if (!tracker[selectedUrl]) {
        tracker[selectedUrl] = {};
    }
    tracker[selectedUrl].follow_up_date = fDate.toISOString();
    
    // Save to backend and re-render sidebar visually
    saveLeadTracking(false).then(() => {
        alert(`CRM Reminder: Follow-up actively set for ${fDate.toLocaleString()}`);
    });
};

async function saveLeadTracking(showFeedback = true) {
    if (!selectedUrl) return;

    const data = {
        url: selectedUrl,
        contacted: contactedCheckbox.checked,
        contacted_date: contactedCheckbox.checked ? new Date().toISOString().split('T')[0] : null,
        outreach_channel: outreachChannelSelect.value,
        notes: contactNotes.value,
        custom_strategy: tracker[selectedUrl]?.custom_strategy || null,
        follow_up_date: tracker[selectedUrl]?.follow_up_date || null
    };

    try {
        const response = await fetch('/api/tracker', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            const resData = await response.json();
            tracker[selectedUrl] = resData.data;
            
            // Re-render components to show status update
            renderLeadsList();
            renderMetrics();

            if (showFeedback) {
                saveStatus.classList.add('show');
                setTimeout(() => saveStatus.classList.remove('show'), 2000);
            }
        } else {
            console.error('Failed to save tracker data');
        }
    } catch (err) {
        console.error('Error saving tracking data:', err);
    }
}

async function generateStrategy() {
    if (!selectedUrl) return;

    const lead = leads[selectedUrl];
    
    // Find best social link for prompt
    let bestSocial = '';
    const socials = lead.socials || {};
    if (socials.linkedin) bestSocial = 'LinkedIn';
    else if (socials.instagram) bestSocial = 'Instagram';
    else if (socials.twitter) bestSocial = 'Twitter/X';
    else if (lead.verified_emails && lead.verified_emails.length > 0) bestSocial = 'Email';

    const reqData = {
        url: selectedUrl,
        profile: lead.profile,
        channel_name: lead.channel_name || lead.profile,
        best_social: bestSocial,
        websites: lead.websites || []
    };

    // Show loading
    if (aiEmpty) aiEmpty.classList.add('hidden');
    if (aiResult) aiResult.classList.add('hidden');
    if (aiLoading) aiLoading.classList.remove('hidden');
    generateStrategyBtn.disabled = true;

    try {
        const response = await fetch('/api/generate_strategy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(reqData)
        });

        if (response.ok) {
            const strategy = await response.json();
            
            // Update local tracker cache
            if (!tracker[selectedUrl]) {
                tracker[selectedUrl] = {};
            }
            tracker[selectedUrl].custom_strategy = strategy;
            
            renderStrategy(strategy);
            lucide.createIcons();
        } else {
            const errorData = await response.json();
            alert(`Error generating strategy: ${errorData.error || 'Server error'}`);
            renderStrategy(tracker[selectedUrl]?.custom_strategy);
        }
    } catch (err) {
        console.error('Error generating strategy:', err);
        alert('Server connection error. Failed to reach OpenAI API.');
        renderStrategy(tracker[selectedUrl]?.custom_strategy);
    }
}

// --- CLIPPER ENGINE LOGIC ---
document.addEventListener('DOMContentLoaded', () => {
    // Tab Elements
    const tabCrmBtn = document.getElementById('tab-crm-btn');
    const tabClipperBtn = document.getElementById('tab-clipper-btn');
    const tabScoutBtn = document.getElementById('tab-scout-btn');
    
    const crmSidebar = document.getElementById('crm-sidebar');
    const clipperSidebar = document.getElementById('clipper-sidebar');
    const scoutSidebar = document.getElementById('scout-sidebar');
    
    const crmMainView = document.getElementById('crm-main-view');
    const clipperMainView = document.getElementById('clipper-main-view');
    const scoutMainView = document.getElementById('scout-main-view');
    
    // Clipper Elements
    const clipperProfile = document.getElementById('clipper-profile');
    const clipperPlatform = document.getElementById('clipper-platform');
    const clipperUrl = document.getElementById('clipper-url');
    const clipperAnalyzeBtn = document.getElementById('clipper-analyze-btn');
    const consoleWindow = document.getElementById('console-window');
    const consoleStatus = document.getElementById('console-status');

    // Scout Elements
    const scoutUrl = document.getElementById('scout-url');
    const scoutRunBtn = document.getElementById('scout-run-btn');
    const scoutGrid = document.getElementById('scout-grid');
    const scoutLoading = document.getElementById('scout-loading');
    const scoutInputLabel = document.getElementById('scout-input-label');
    const scoutModeRadios = document.querySelectorAll('input[name="scout-mode"]');

    if (scoutModeRadios.length > 0) {
        scoutModeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (e.target.value === 'search') {
                    scoutInputLabel.textContent = "Search Niche Keyword";
                    scoutUrl.placeholder = "e.g., Finance Podcast Shorts";
                } else {
                    scoutInputLabel.textContent = "Competitor Channel URL";
                    scoutUrl.placeholder = "https://youtube.com/@mkbhd";
                }
            });
        });
    }

    let logPollInterval = null;

    // Tab Switching
    function switchTab(tab) {
        [tabCrmBtn, tabClipperBtn, tabScoutBtn].forEach(b => b?.classList.remove('active'));
        [crmSidebar, clipperSidebar, scoutSidebar].forEach(s => s?.classList.add('hidden'));
        [crmMainView, clipperMainView, scoutMainView].forEach(v => v?.classList.add('hidden'));

        if (tab === 'crm') {
            tabCrmBtn?.classList.add('active');
            crmSidebar?.classList.remove('hidden');
            crmMainView?.classList.remove('hidden');
        } else if (tab === 'clipper') {
            tabClipperBtn?.classList.add('active');
            clipperSidebar?.classList.remove('hidden');
            clipperMainView?.classList.remove('hidden');
            if (clipperProfile && clipperProfile.options.length <= 1) loadClipperProfiles();
        } else if (tab === 'scout') {
            tabScoutBtn?.classList.add('active');
            scoutSidebar?.classList.remove('hidden');
            scoutMainView?.classList.remove('hidden');
        }
    }

    if(tabCrmBtn) tabCrmBtn.addEventListener('click', () => switchTab('crm'));
    if(tabClipperBtn) tabClipperBtn.addEventListener('click', () => switchTab('clipper'));
    if(tabScoutBtn) tabScoutBtn.addEventListener('click', () => switchTab('scout'));

    let profileStyles = {};

    // Fetch Profiles
    async function loadClipperProfiles() {
        try {
            const res = await fetch('/api/profiles');
            if (res.ok) {
                const data = await res.json();
                profileStyles = data.profile_styles || {};
                clipperProfile.innerHTML = data.profiles.map(p => `<option value="${p}">${p}</option>`).join('');
                clipperPlatform.innerHTML = data.platforms.map(p => `<option value="${p}">${p}</option>`).join('');
                syncPlatform();
            }
        } catch (e) {
            console.error("Failed to load profiles");
        }
    }

    function syncPlatform() {
        const profileName = clipperProfile.value;
        const leadKey = Object.keys(leads).find(url => leads[url].profile === profileName || leads[url].channel_name === profileName);
        if (leadKey) {
            const platform = leads[leadKey].target_platform || 'tiktok';
            clipperPlatform.value = platform.toLowerCase();
            console.log(`Auto-selected platform ${platform} for ${profileName}`);
        }
    }



    if(clipperProfile) {
        clipperProfile.addEventListener('change', () => {
            syncPlatform();
        });
    }

    // Analyze Pipeline
    if(clipperAnalyzeBtn) {
        clipperAnalyzeBtn.addEventListener('click', async () => {
            const url = clipperUrl.value.trim();
            if (!url) return alert("Please enter a YouTube URL");

            clipperAnalyzeBtn.disabled = true;
            clipperAnalyzeBtn.innerHTML = "Analyzing...";
            consoleStatus.textContent = "Status: Analyzing Hooks...";
            document.getElementById('clipper-hooks-container').classList.add('hidden');
            consoleWindow.textContent = "";

            try {
                const res = await fetch('/api/pipeline/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        youtube_url: url,
                        profile: clipperProfile.value,
                        platform: clipperPlatform.value
                    })
                });
                if (!res.ok) {
                    alert("Failed to start analysis");
                    clipperAnalyzeBtn.disabled = false;
                    clipperAnalyzeBtn.innerHTML = `<i data-lucide="search"></i> Find Viral Hooks`;
                    consoleStatus.textContent = "Status: Error";
                    return;
                }
                startPollingLogs(true);
            } catch (e) {
                console.error(e);
                clipperAnalyzeBtn.disabled = false;
            }
        });
    }

    function renderHookCards(data) {
        if(!data || !data.clips || data.clips.length === 0) return;
        window.currentHooksData = data;
        
        const container = document.getElementById('clipper-hooks-container');
        const grid = document.getElementById('hooks-grid');
        if(!container || !grid) return;
        
        container.classList.remove('hidden');
        grid.innerHTML = '';
        
        data.clips.forEach((clip, index) => {
            const card = document.createElement('div');
            card.className = 'glass-card';
            card.style.padding = '15px';
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" class="batch-select-checkbox" checked style="width: 16px; height: 16px; cursor: pointer;" title="Select for Batch Render">
                        <h3 style="color: var(--accent-cyan); margin:0; font-size: 16px;">Clip ${index + 1} (${clip.score}/10)</h3>
                    </div>
                    <span style="background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; font-size: 11px;">${Number(clip.start).toFixed(1)}s - ${Number(clip.end).toFixed(1)}s</span>
                </div>
                <p style="font-size: 13px; color: white; font-weight: 500; margin-bottom: 5px;">${clip.emotion || clip.hook_type || 'Viral Hook'}</p>
                <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 15px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;" title="${clip.reason}">${clip.reason}</p>
                
                <div class="input-group" style="margin-bottom: 10px;">
                    <label style="font-size: 11px; margin-bottom: 4px;">Format Style</label>
                    <select class="clip-format-select" style="font-size: 12px; padding: 6px;">
                        <option value="blur_bg">Premium (Blurry Background)</option>
                        <option value="split_screen">Retention (Split-Screen)</option>
                        <option value="letterbox">Educational (Letterbox)</option>
                        <option value="auto">Auto (Face-Track)</option>
                    </select>
                </div>
                
                <div class="input-group clip-retention-group" style="margin-bottom: 10px; display: none;">
                    <label style="font-size: 11px; margin-bottom: 4px;">Retention Style</label>
                    <select class="clip-retention-select" style="font-size: 12px; padding: 6px; background-color: var(--bg-darker); border: 1px solid var(--border-color); color: white; border-radius: 4px; width: 100%;">
                        <option value="high_stimulus">🎮 High Stimulus (Gaming)</option>
                        <option value="asmr">🧼 Oddly Satisfying (ASMR)</option>
                        <option value="premium">✨ Premium Cinematic (3D Loops)</option>
                    </select>
                </div>
                
                <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; margin-bottom: 5px; cursor: pointer; color: white;">
                    <input type="checkbox" class="clip-subtitles-checkbox" checked> Enable Dynamic Subtitles
                </label>
                <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; margin-bottom: 15px; cursor: pointer; color: white;">
                    <input type="checkbox" class="clip-watermark-checkbox" checked> Enable NucciTech Watermark
                </label>
                
                <button class="btn btn-primary render-clip-btn" style="width: 100%; font-size: 13px; height: 36px;">
                    <i data-lucide="video"></i> Render Clip
                </button>
            `;
            
            const renderBtn = card.querySelector('.render-clip-btn');
            const formatSelect = card.querySelector('.clip-format-select');
            const retentionGroup = card.querySelector('.clip-retention-group');
            const retentionSelect = card.querySelector('.clip-retention-select');
            const subsCheckbox = card.querySelector('.clip-subtitles-checkbox');
            const watermarkCheckbox = card.querySelector('.clip-watermark-checkbox');
            
            formatSelect.addEventListener('change', () => {
                if (formatSelect.value === 'split_screen') {
                    retentionGroup.style.display = 'block';
                } else {
                    retentionGroup.style.display = 'none';
                }
            });
            renderBtn.addEventListener('click', async () => {
                renderBtn.disabled = true;
                renderBtn.innerHTML = "Rendering...";
                consoleWindow.textContent = "";
                consoleStatus.textContent = "Status: Rendering Clip " + (index+1) + "...";
                
                try {
                    const res = await fetch('/api/pipeline/render', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            video_id: data.video_id,
                            video_filepath: data.video_filepath,
                            clip_data: clip,
                            profile_name: data.profile_name,
                            platform: data.platform,
                            style_overrides: {
                                crop_strategy: formatSelect.value,
                                retention_category: retentionSelect.value,
                                use_subtitles: subsCheckbox.checked,
                                use_watermark: watermarkCheckbox.checked
                            }
                        })
                    });
                    if(res.ok) {
                        startPollingLogs(false);
                    } else {
                        renderBtn.innerHTML = "Error";
                        renderBtn.disabled = false;
                    }
                } catch(e) {
                    console.error(e);
                    renderBtn.innerHTML = "Error";
                    renderBtn.disabled = false;
                }
            });
            
            grid.appendChild(card);
        });
        lucide.createIcons();
    }

    function startPollingLogs(isAnalyze = false) {
        if (logPollInterval) clearInterval(logPollInterval);
        logPollInterval = setInterval(async () => {
            try {
                const res = await fetch('/api/logs');
                if (res.ok) {
                    const data = await res.json();
                    if (data.logs) {
                        let cleanLogs = data.logs;
                        if (isAnalyze) {
                            const match = cleanLogs.match(/__ANALYZE_RESULT__=(.*)/);
                            if(match) {
                                try {
                                    const analyzeData = JSON.parse(match[1].trim());
                                    renderHookCards(analyzeData);
                                } catch(e) { console.error("Failed to parse", e); }
                                cleanLogs = cleanLogs.replace(/__ANALYZE_RESULT__=.*/, '');
                            }
                        }
                        if (cleanLogs.trim()) {
                            consoleWindow.textContent += cleanLogs;
                            consoleWindow.scrollTop = consoleWindow.scrollHeight;
                            
                            const matchPercentage = cleanLogs.match(/(\d+)%/g);
                            if (matchPercentage && matchPercentage.length > 0) {
                                const lastPercent = matchPercentage[matchPercentage.length - 1];
                                const container = document.getElementById('render-progress-container');
                                const bar = document.getElementById('render-progress-bar');
                                if (container && bar) {
                                    container.style.display = 'block';
                                    bar.style.width = lastPercent;
                                }
                            }
                        }
                    }
                    if (!data.running) {
                        clearInterval(logPollInterval);
                        if (isAnalyze) {
                            const btn = document.getElementById('clipper-analyze-btn');
                            if(btn) {
                                btn.disabled = false;
                                btn.innerHTML = `<i data-lucide="search"></i> Find Viral Hooks`;
                            }
                        }
                        consoleStatus.textContent = "Status: Done";
                        lucide.createIcons();
                        lucide.createIcons();
                        document.querySelectorAll('.render-clip-btn').forEach(b => {
                            if (b.disabled && b.innerHTML === "Rendering...") {
                                b.innerHTML = `<i data-lucide="video"></i> Render Clip`;
                                b.disabled = false;
                            }
                        });
                        const batchBtn = document.getElementById('batch-render-btn');
                        if (batchBtn && batchBtn.disabled) {
                            batchBtn.disabled = false;
                            batchBtn.innerHTML = '<i data-lucide="layers"></i> Batch Render Selected';
                        }
                        const container = document.getElementById('render-progress-container');
                        if (container) container.style.display = 'none';
                        lucide.createIcons();
                    }
                }
            } catch (e) {
                console.error("Log poll error", e);
            }
        }, 500);
    }

    // --- SCOUT LOGIC ---
    if(scoutRunBtn) {
        scoutRunBtn.addEventListener('click', async () => {
            const url = scoutUrl.value.trim();
            const mode = document.querySelector('input[name="scout-mode"]:checked').value;
            
            if(!url) {
                return alert(mode === 'search' ? "Please enter a search keyword" : "Please enter a competitor channel URL");
            }
            
            if(mode === 'channel' && !url.includes('youtube.com') && !url.includes('youtu.be')) {
                return alert("You are in 'Specific Channel' mode. Please enter a valid YouTube URL, or click 'Discover Niche' to search by keyword.");
            }
            
            scoutRunBtn.disabled = true;
            scoutRunBtn.innerHTML = "Scanning...";
            scoutGrid.innerHTML = "";
            scoutLoading.classList.remove('hidden');
            
            try {
                const res = await fetch('/api/scout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: url, mode: mode })
                });
                const data = await res.json();
                scoutLoading.classList.add('hidden');
                
                if(!res.ok) {
                    scoutGrid.innerHTML = `<h2 style="color: red;">ERROR: ${data.error || "Scout failed"}</h2>`;
                } else {
                    if (data.competitors) {
                        if (data.competitors.length === 0) {
                            scoutGrid.innerHTML = `<h2 style="color: orange; padding: 20px;">0 Competitors found. YouTube might be blocking the search or no results match the keyword. Try a different keyword.</h2>`;
                        } else {
                            renderCompetitors(data.competitors);
                        }
                    } else {
                        if ((data.shorts || []).length === 0) {
                            scoutGrid.innerHTML = `<h2 style="color: orange; padding: 20px;">0 Shorts found on this channel. Either it has no shorts or it's an invalid channel.</h2>`;
                        } else {
                            renderScoutShorts(data.shorts || []);
                        }
                    }
                }
            } catch(e) {
                console.error(e);
                scoutLoading.classList.add('hidden');
                alert("Server error occurred.");
            }
            scoutRunBtn.disabled = false;
            scoutRunBtn.innerHTML = `<i data-lucide="search"></i> Scan Channel`;
            lucide.createIcons();
        });
    }

    function renderScoutShorts(shorts) {
        if(!shorts || shorts.length === 0) {
            scoutGrid.innerHTML = "<p style='color:var(--text-muted);'>No viral shorts found.</p>";
            return;
        }
        
        scoutGrid.innerHTML = shorts.map((s, i) => {
            const title = s.title || 'Unknown Title';
            const safeTitle = title.replace(/"/g, '&quot;');
            const channelName = s.channel_name ? `<span style="display:block; color:var(--text-muted); font-size:12px; margin-bottom:4px;"><i data-lucide="user" style="width:10px;height:10px;"></i> ${s.channel_name}</span>` : '';
            const safeUrl = s.url || '#';
            
            const safeChannelName = s.channel_name ? s.channel_name.replace(/"/g, '&quot;') : 'Unknown';
            const safeChannelUrl = s.channel_url ? s.channel_url.replace(/'/g, "\\'") : '';

            return `
            <div class="niche-card">
                <img src="${s.thumbnail || ''}" alt="Thumbnail">
                <div class="niche-card-body">
                    <div class="scout-views"><i data-lucide="eye"></i> ${s.formatted_views} views</div>
                    ${channelName}
                    <div class="scout-card-title" title="${safeTitle}">${title}</div>
                    <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                        <a href="${safeUrl}" target="_blank" style="color: var(--accent-purple); font-size: 12px; text-decoration: none;">View Original <i data-lucide="external-link" style="width:12px;height:12px;vertical-align:middle;"></i></a>
                        ${safeChannelUrl ? `<a href="#" style="color: var(--accent-cyan); font-size: 12px; text-decoration: none;" onclick="event.preventDefault(); window.saveLeadToCrm('${safeChannelName}', '${safeChannelUrl}', this)">Save Lead</a>` : ''}
                    </div>
                    <div class="scout-pair-box">
                        <input type="text" id="source-${i}" placeholder="Paste Source Podcast URL...">
                        <button class="btn btn-outline" style="width: 100%; font-size: 12px; padding: 6px;" onclick="window.startCloneAndTrain('${safeUrl}', document.getElementById('source-${i}').value, this)">Clone & Train</button>
                    </div>
                </div>
            </div>
            `;
        }).join('');
        lucide.createIcons();
    }

    function renderCompetitors(competitors) {
        if(!competitors || competitors.length === 0) {
            scoutGrid.innerHTML = "<p style='color:var(--text-muted);'>No competitors found for this niche.</p>";
            return;
        }
        
        scoutGrid.innerHTML = competitors.map((c, i) => {
            const name = c.name || 'Unknown Channel';
            const safeName = name.replace(/"/g, '&quot;');
            const safeUrl = c.url ? c.url.replace(/'/g, "\\'") : '';
            
            return `
            <div class="niche-card" style="background: rgba(16, 185, 129, 0.05); border-color: rgba(16, 185, 129, 0.2);">
                <div class="niche-card-body" style="height: 100%;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                        <h3 style="margin: 0; color: white;">${safeName}</h3>
                        <div class="scout-views" style="color: var(--accent-green);"><i data-lucide="trending-up"></i> Top Target</div>
                    </div>
                    
                    <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 15px;">
                        <strong>${c.formatted_views} Total Views</strong> across ${c.hit_count} viral shorts in this niche.
                    </div>
                    
                    <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 15px; border-left: 2px solid var(--accent-purple); padding-left: 10px;">
                        <strong>Most Viral Short:</strong><br/>
                        ${c.top_short_title || 'Unknown'}
                    </div>
                    
                    <div style="display: flex; gap: 10px; margin-top: auto; flex-direction: column;">
                        <button class="btn btn-outline" style="width: 100%; font-size: 12px; padding: 8px; border-color: var(--accent-cyan); color: var(--accent-cyan);" onclick="window.saveLeadToCrm('${safeName}', '${safeUrl}', this)"><i data-lucide="bookmark"></i> Save to CRM</button>
                        <div style="display: flex; gap: 10px;">
                            <a href="${c.url || '#'}" target="_blank" class="btn btn-outline" style="flex: 1; text-align: center; font-size: 12px; padding: 8px;">View Channel</a>
                            <button class="btn btn-primary" style="flex: 1; font-size: 12px; padding: 8px;" onclick="document.getElementById('scout-url').value='${safeUrl}'; document.querySelector('input[name=\\'scout-mode\\'][value=\\'channel\\']').click(); document.getElementById('scout-run-btn').click();">Scan Library</button>
                        </div>
                    </div>
                </div>
            </div>
            `;
        }).join('');
        lucide.createIcons();
    }
    
    window.saveLeadToCrm = async function(name, url, btn) {
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i data-lucide="loader" style="animation: spin 2s linear infinite;"></i> Saving...';
        lucide.createIcons();
        btn.disabled = true;
        
        try {
            const res = await fetch('/api/contacts', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({channel_name: name, channel_url: url})
            });
            if (res.ok) {
                btn.innerHTML = '<i data-lucide="check"></i> Saved to CRM';
                btn.style.backgroundColor = 'var(--accent-green)';
                btn.style.color = 'black';
                btn.style.borderColor = 'var(--accent-green)';
                lucide.createIcons();
                // Optionally reload the CRM data so it shows up instantly!
                loadData();
            } else {
                btn.innerHTML = '<i data-lucide="alert-circle"></i> Error';
                btn.disabled = false;
            }
        } catch (e) {
            btn.innerHTML = '<i data-lucide="alert-circle"></i> Error';
            btn.disabled = false;
        }
    };
    
    window.startCloneAndTrain = async function(shortUrl, sourceUrl, btn) {
        if (!sourceUrl || sourceUrl.trim() === '') {
            alert("Please paste the original source podcast URL first!");
            return;
        }
        
        btn.innerHTML = '<i data-lucide="loader" style="animation: spin 2s linear infinite;"></i> Starting...';
        lucide.createIcons();
        btn.disabled = true;
        
        try {
            const res = await fetch('/api/train', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({short_url: shortUrl, source_url: sourceUrl.trim()})
            });
            const data = await res.json();
            
            if (res.ok && data.success) {
                btn.innerHTML = '<i data-lucide="check"></i> Pipeline Started';
                lucide.createIcons();
                // Switch to console tab to watch progress
                document.getElementById('tab-clipper-btn').click();
            } else {
                alert(data.error || "Failed to start pipeline");
                btn.innerHTML = 'Clone & Train';
                btn.disabled = false;
            }
        } catch(e) {
            alert("Error connecting to server.");
            btn.innerHTML = 'Clone & Train';
            btn.disabled = false;
        }
    };

    window.findGatekeeper = async function() {
        const btn = document.getElementById('gatekeeper-search-btn');
        const resultsDiv = document.getElementById('gatekeeper-results');
        
        // Grab current target's name from the header (e.g. Lead Detail Name)
        const nameEl = document.getElementById('lead-detail-name');
        if (!nameEl) {
            alert('Please select a creator first!');
            return;
        }
        
        const channelName = nameEl.innerText;
        
        btn.innerHTML = '<i data-lucide="loader" style="animation: spin 2s linear infinite;"></i> Hunting...';
        lucide.createIcons();
        btn.disabled = true;
        resultsDiv.classList.add('hidden');
        resultsDiv.innerHTML = '';
        
        try {
            const res = await fetch('/api/gatekeeper', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({channel_name: channelName})
            });
            const data = await res.json();
            
            if (data.success && data.gatekeepers && data.gatekeepers.length > 0) {
                let html = '<strong>Found Potential Gatekeepers:</strong><ul style="margin-top: 5px; margin-bottom: 0; padding-left: 20px;">';
                data.gatekeepers.forEach(g => {
                    html += `<li><a href="${g.url}" target="_blank" style="color: var(--accent-cyan); text-decoration: none;">${g.name}</a></li>`;
                });
                html += '</ul>';
                resultsDiv.innerHTML = html;
                resultsDiv.classList.remove('hidden');
            } else {
                resultsDiv.innerHTML = '<span style="color: var(--accent-red);">No obvious gatekeepers found. Try manual search.</span>';
                resultsDiv.classList.remove('hidden');
            }
        } catch(e) {
            alert('Error connecting to scraper API');
        } finally {
            btn.innerHTML = '<i data-lucide="search"></i> Hunt Gatekeeper on LinkedIn';
            lucide.createIcons();
            btn.disabled = false;
        }
    };
    const retDownloadBtn = document.getElementById('download-retention-btn');
    if (retDownloadBtn) {
        retDownloadBtn.addEventListener('click', async () => {
            const urlInput = document.getElementById('retention-url');
            const catSelect = document.getElementById('retention-cat');
            const statusDiv = document.getElementById('retention-download-status');
            
            if (!urlInput.value) {
                alert("Please enter a YouTube URL");
                return;
            }
            
            statusDiv.style.display = 'block';
            retDownloadBtn.disabled = true;
            
            try {
                await fetch('/api/retention/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        url: urlInput.value,
                        category: catSelect.value
                    })
                });
                urlInput.value = "";
                setTimeout(() => {
                    retDownloadBtn.disabled = false;
                    statusDiv.style.display = 'none';
                }, 5000);
            } catch(e) {
                alert("Error starting download.");
                retDownloadBtn.disabled = false;
            }
        });
    }

    const batchRenderBtn = document.getElementById('batch-render-btn');
    if (batchRenderBtn) {
        batchRenderBtn.addEventListener('click', async () => {
            const cards = document.querySelectorAll('#hooks-grid .glass-card');
            const selectedClips = [];
            
            cards.forEach((card, idx) => {
                const checkbox = card.querySelector('.batch-select-checkbox');
                if (checkbox && checkbox.checked) {
                    const formatSelect = card.querySelector('.clip-format-select');
                    const retentionSelect = card.querySelector('.clip-retention-select');
                    const subsCheckbox = card.querySelector('.clip-subtitles-checkbox');
                    const watermarkCheckbox = card.querySelector('.clip-watermark-checkbox');
                    
                    // Retrieve original clip data from a hidden attribute or by index if we had a global
                    // For now, let's inject it into the DOM so we can read it, or use the global `window.currentHooksData`
                    if (window.currentHooksData && window.currentHooksData.clips[idx]) {
                        selectedClips.push({
                            clip_data: window.currentHooksData.clips[idx],
                            style_overrides: {
                                crop_strategy: formatSelect.value,
                                retention_category: retentionSelect.value,
                                use_subtitles: subsCheckbox.checked,
                                use_watermark: watermarkCheckbox.checked
                            }
                        });
                    }
                }
            });
            
            if (selectedClips.length === 0) {
                alert("Please select at least one clip to render.");
                return;
            }
            
            batchRenderBtn.disabled = true;
            batchRenderBtn.innerHTML = '<i data-lucide="loader" style="animation: spin 2s linear infinite;"></i> Rendering Batch...';
            lucide.createIcons();
            
            consoleWindow.textContent = "";
            consoleStatus.textContent = `Status: Batch Rendering ${selectedClips.length} clips...`;
            
            try {
                const res = await fetch('/api/pipeline/batch_render', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        video_id: window.currentHooksData.video_id,
                        video_filepath: window.currentHooksData.video_filepath,
                        profile_name: window.currentHooksData.profile_name,
                        platform: window.currentHooksData.platform,
                        clips: selectedClips
                    })
                });
                
                if (res.ok) {
                    startPollingLogs(false);
                } else {
                    alert("Batch rendering failed to start.");
                }
            } catch(e) {
                alert("Error connecting to server for batch render.");
            } finally {
                batchRenderBtn.disabled = false;
                batchRenderBtn.innerHTML = '<i data-lucide="layers"></i> Batch Render Selected';
                lucide.createIcons();
            }
        });
    }

});

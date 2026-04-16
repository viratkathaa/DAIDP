/* ─── AI Ad Generator — Frontend Application ──────── */

const API = '';
const app = {
    campaignId: null,
    state: {},
    apiCalls: 0,
    currentRefine: null,
};

const EXAMPLE_BRIEFS = {
    nike: {
        brand_name: 'Nike',
        product_name: 'Pegasus Turbo Next',
        product_description: 'A high-performance running shoe designed for urban runners who want speed, responsive cushioning, and street-ready style.',
        target_market: 'Young urban runners and style-conscious fitness consumers',
        marketing_objectives: 'Drive launch awareness, boost product consideration, and increase online purchases',
        platform: 'instagram',
        budget_tier: 'high',
        brand_guidelines: 'Bold, kinetic, premium, aspirational, black-white-orange palette',
        prohibited_claims: '',
        competitors: 'Adidas, New Balance',
    },
    coffee: {
        brand_name: 'Volt Brew',
        product_name: 'Cold Charge RTD',
        product_description: 'A ready-to-drink caffeinated coffee beverage that blends energy-drink intensity with premium iced coffee taste for busy professionals and creators.',
        target_market: 'Busy professionals, creators, and on-the-go consumers needing clean energy',
        marketing_objectives: 'Drive trial, build brand awareness, and increase repeat purchase intent',
        platform: 'instagram',
        budget_tier: 'mid',
        brand_guidelines: 'Modern, sharp, fast-paced, premium convenience, silver and espresso tones',
        prohibited_claims: 'Guaranteed productivity boosts',
        competitors: 'Red Bull, Monster, Starbucks',
    },
    beauty: {
        brand_name: 'Luma Skin',
        product_name: 'Radiant Ritual Collection',
        product_description: 'A premium skincare and makeup line centered on radiant skin, confidence, and elevated daily beauty rituals.',
        target_market: 'Beauty-conscious consumers seeking premium daily skincare and makeup rituals',
        marketing_objectives: 'Increase brand desirability, drive collection sales, and improve social engagement',
        platform: 'instagram',
        budget_tier: 'high',
        brand_guidelines: 'Polished, luxurious, emotionally resonant, soft neutrals and gold accents',
        prohibited_claims: 'Guaranteed skin transformation',
        competitors: 'Rare Beauty, Charlotte Tilbury, Fenty Beauty',
    }
};

/* ─── Utilities ────────────────────────────────────── */
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function showToast(msg, type = '') {
    const t = $('#toast');
    t.textContent = msg;
    t.className = 'toast ' + type;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3000);
}

function setLoading(btnId, loading) {
    const btn = typeof btnId === 'string' ? $(`#${btnId}`) : btnId;
    if (!btn) return;
    const text = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.btn-loader');
    if (loading) {
        btn.disabled = true;
        if (text) text.classList.add('hidden');
        if (loader) loader.classList.remove('hidden');
    } else {
        btn.disabled = false;
        if (text) text.classList.remove('hidden');
        if (loader) loader.classList.add('hidden');
    }
}

async function apiCall(method, path, body = null) {
    app.apiCalls++;
    $('#apiCalls').textContent = app.apiCalls;
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || 'API error');
    }
    return res.json();
}

async function apiCallForm(path, formData) {
    app.apiCalls++;
    $('#apiCalls').textContent = app.apiCalls;
    const res = await fetch(API + path, { method: 'POST', body: formData });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || 'API error');
    }
    return res.json();
}

/* ─── Navigation ───────────────────────────────────── */
const STEPS = ['brief', 'personas', 'angles', 'scripts', 'storyboards', 'evaluation', 'video-generation', 'video-evaluation'];

app.goToStep = function(step) {
    $$('.step-panel').forEach(p => p.classList.remove('active'));
    $(`#panel-${step}`).classList.add('active');
    $$('.nav-item').forEach(n => n.classList.remove('active'));
    $(`.nav-item[data-step="${step}"]`).classList.add('active');
};

$$('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        const step = item.dataset.step;
        if (
            step === 'brief' ||
            app.state[step] ||
            (step === 'evaluation' && app.state.evaluation) ||
            (step === 'video-generation' && (app.state['video-generation'] || app.state.evaluation)) ||
            (step === 'video-evaluation' && (app.state['video-evaluation'] || app.state['video-generation'] || app.state.videoEvaluation))
        ) {
            app.goToStep(step);
        }
    });
});

function markStepCompleted(step) {
    const nav = $(`.nav-item[data-step="${step}"]`);
    nav.classList.add('completed');
    nav.querySelector('.step-status').innerHTML = '&#10003;';
}

function updateTime(timeSec) {
    const total = Object.values(app.state.metrics || {})
        .filter(v => typeof v === 'number')
        .reduce((a, b) => a + b, 0);
    $('#totalTime').textContent = total.toFixed(1) + 's';
}

function applyExampleBrief(exampleKey) {
    const brief = EXAMPLE_BRIEFS[exampleKey];
    if (!brief) return;
    $('#brand_name').value = brief.brand_name;
    $('#product_name').value = brief.product_name;
    $('#product_description').value = brief.product_description;
    $('#target_market').value = brief.target_market;
    $('#marketing_objectives').value = brief.marketing_objectives;
    $('#platform').value = brief.platform;
    $('#budget_tier').value = brief.budget_tier;
    $('#brand_guidelines').value = brief.brand_guidelines;
    $('#prohibited_claims').value = brief.prohibited_claims;
    $('#competitors').value = brief.competitors;
    $$('.example-preset').forEach(btn => btn.classList.toggle('active', btn.dataset.example === exampleKey));
    showToast('Example brief loaded.', 'success');
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* ─── Step 1: Submit Brief ─────────────────────────── */
$('#briefForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    setLoading('submitBrief', true);
    try {
        const brief = {
            brand_name: $('#brand_name').value,
            product_name: $('#product_name').value,
            product_description: $('#product_description').value,
            target_market: $('#target_market').value,
            marketing_objectives: $('#marketing_objectives').value,
            platform: $('#platform').value,
            budget_tier: $('#budget_tier').value,
            brand_guidelines: $('#brand_guidelines').value,
            prohibited_claims: $('#prohibited_claims').value,
            competitors: $('#competitors').value,
        };

        // Create campaign
        const res = await apiCall('POST', '/api/campaign', brief);
        app.campaignId = res.campaign_id;
        app.state.brief = brief;
        app.state.metrics = {};
        showToast('Campaign created! Generating personas...', 'success');
        markStepCompleted('brief');

        // Auto-generate personas
        const pRes = await apiCall('POST', `/api/generate/${app.campaignId}/personas`);
        app.state.personas = pRes.personas;
        app.state.metrics.personas_time = pRes.time_taken;
        updateTime();
        renderPersonas(pRes.personas, pRes.constraints);
        markStepCompleted('personas');
        app.goToStep('personas');
        showToast(`Personas generated in ${pRes.time_taken}s`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('submitBrief', false);
});

/* ─── Step 2: Render Personas ──────────────────────── */
function renderPersonas(personas, constraints) {
    const grid = $('#personasGrid');
    grid.innerHTML = personas.map((p, i) => `
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">${p.name}</div>
                    <div class="card-subtitle">${p.age_range} &middot; ${p.occupation}</div>
                </div>
                <span class="card-badge badge-persona">Persona ${i + 1}</span>
            </div>
            <div class="card-body">
                <p>${p.persona_summary}</p>
                <div style="margin-top:12px">
                    <strong>Pain Points</strong>
                    <div class="tag-list">${p.pain_points.map(t => `<span class="tag">${t}</span>`).join('')}</div>
                </div>
                <div style="margin-top:12px">
                    <strong>Interests</strong>
                    <div class="tag-list">${p.interests.map(t => `<span class="tag">${t}</span>`).join('')}</div>
                </div>
                <div style="margin-top:12px">
                    <strong>Media Habits</strong>
                    <div class="tag-list">${p.media_habits.map(t => `<span class="tag">${t}</span>`).join('')}</div>
                </div>
                <div style="margin-top:12px">
                    <strong>Buying Motivation:</strong> ${p.buying_motivation}
                </div>
            </div>
            <div class="card-actions">
                <button class="btn btn-outline btn-sm" onclick="app.openRefinement('personas', ${i}, '${p.name}')">Refine</button>
            </div>
        </div>
    `).join('');
    renderConstraintBadge('personas', constraints.personas);
}

/* ─── Step 3: Generate & Render Angles ─────────────── */
app.generateAngles = async function() {
    setLoading('genAnglesBtn', true);
    try {
        const res = await apiCall('POST', `/api/generate/${app.campaignId}/angles`);
        app.state.angles = res.angles;
        app.state.metrics.angles_time = res.time_taken;
        updateTime();
        renderAngles(res.angles, res.constraints);
        markStepCompleted('angles');
        app.goToStep('angles');
        showToast(`Angles generated in ${res.time_taken}s`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('genAnglesBtn', false);
};

function renderAngles(angles, constraints) {
    const grid = $('#anglesGrid');
    grid.innerHTML = angles.map((a, i) => `
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">${a.angle_name}</div>
                    <div class="card-subtitle">Target: ${a.target_persona}</div>
                </div>
                <span class="card-badge badge-angle">${a.emotional_trigger}</span>
            </div>
            <div class="card-body">
                <div style="margin-bottom:12px">
                    <strong>Hook:</strong>
                    <p style="font-size:16px;font-style:italic;color:var(--primary);margin-top:4px">"${a.hook}"</p>
                </div>
                <div style="margin-bottom:12px">
                    <strong>Value Proposition:</strong>
                    <p>${a.value_proposition}</p>
                </div>
                <div>
                    <strong>CTA:</strong>
                    <p style="font-weight:600;color:var(--secondary)">${a.cta}</p>
                </div>
            </div>
            <div class="card-actions">
                <button class="btn btn-outline btn-sm" onclick="app.openRefinement('angles', ${i}, '${a.angle_name}')">Refine</button>
            </div>
        </div>
    `).join('');
    renderConstraintBadge('angles', constraints.angles);
}

/* ─── Step 4: Generate & Render Scripts ────────────── */
app.generateScripts = async function() {
    setLoading('genScriptsBtn', true);
    try {
        const res = await apiCall('POST', `/api/generate/${app.campaignId}/scripts`);
        app.state.scripts = res.scripts;
        app.state.metrics.scripts_time = res.time_taken;
        updateTime();
        renderScripts(res.scripts, res.constraints);
        markStepCompleted('scripts');
        app.goToStep('scripts');
        showToast(`Scripts generated in ${res.time_taken}s`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('genScriptsBtn', false);
};

function renderScripts(scripts, constraints) {
    const container = $('#scriptsContainer');
    container.innerHTML = scripts.map((s, si) => `
        <div class="script-block">
            <div class="script-header">
                <div>
                    <h3>${s.concept_name}</h3>
                    <div class="script-meta">
                        <span>&#9654; ${s.duration_seconds}s</span>
                        <span>&#127917; ${s.scenes.length} scenes</span>
                        <span>&#127908; ${s.tone}</span>
                        <span>&#128100; ${s.target_persona}</span>
                    </div>
                </div>
                <button class="btn btn-outline btn-sm" onclick="app.openRefinement('scripts', ${si}, '${s.concept_name}')">Refine</button>
            </div>
            <div class="scene-timeline">
                ${s.scenes.map(sc => `
                    <div class="scene-item">
                        <div class="scene-number">${sc.scene_number}</div>
                        <div class="scene-content">
                            <h4>${sc.duration_seconds}s &mdash; ${sc.camera_direction}</h4>
                            <div class="scene-detail">
                                <div class="scene-field">
                                    <div class="scene-field-label">Visual</div>
                                    <div class="scene-field-value">${sc.visual_description}</div>
                                </div>
                                <div class="scene-field">
                                    <div class="scene-field-label">Narration</div>
                                    <div class="scene-field-value">${sc.narration}</div>
                                </div>
                                <div class="scene-field">
                                    <div class="scene-field-label">On-Screen Text</div>
                                    <div class="scene-field-value">${sc.on_screen_text}</div>
                                </div>
                                <div class="scene-field">
                                    <div class="scene-field-label">Camera</div>
                                    <div class="scene-field-value">${sc.camera_direction}</div>
                                </div>
                                <div class="image-prompt-box">
                                    <div class="scene-field-label">Image Prompt</div>
                                    <div class="scene-field-value">${sc.image_prompt}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
            <div style="padding:0 24px 20px">
                <div style="padding:12px 16px;background:var(--primary-light);border-radius:var(--radius-sm);font-size:14px">
                    <strong>CTA:</strong> ${s.cta_text}
                    ${s.disclaimer ? `<br><span style="font-size:12px;color:var(--text-secondary)">Disclaimer: ${s.disclaimer}</span>` : ''}
                </div>
            </div>
        </div>
    `).join('');
    renderConstraintBadge('scripts', constraints.scripts);
}

/* ─── Step 5: Generate & Render Storyboards ────────── */
app.generateStoryboards = async function() {
    setLoading('genStoryboardsBtn', true);
    try {
        const res = await apiCall('POST', `/api/generate/${app.campaignId}/storyboards`);
        app.state.storyboards = res.storyboards;
        app.state.metrics.storyboards_time = res.time_taken;
        updateTime();
        renderStoryboards(res.storyboards, res.constraints);
        markStepCompleted('storyboards');
        app.goToStep('storyboards');
        showToast(`Storyboards generated in ${res.time_taken}s`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('genStoryboardsBtn', false);
};

function renderStoryboards(storyboards, constraints) {
    const container = $('#storyboardsContainer');
    container.innerHTML = storyboards.map((sb, si) => `
        <div class="storyboard-block">
            <div class="storyboard-header">
                <h3>${sb.script_name}</h3>
                <div class="storyboard-specs">
                    <span class="spec-chip">${sb.format}</span>
                    <span class="spec-chip">${sb.total_duration}s</span>
                    <span class="spec-chip">${sb.typography_style}</span>
                </div>
                <div style="margin-top:8px">
                    <strong style="font-size:13px">Music Mood:</strong>
                    <span style="font-size:13px;color:var(--text-secondary)">${sb.music_mood}</span>
                </div>
                <div class="color-palette">
                    ${sb.color_palette.map(c => `<div class="color-swatch" style="background:${c}" title="${c}"></div>`).join('')}
                </div>
            </div>
            <div class="scene-timeline">
                ${sb.scenes.map(sc => `
                    <div class="scene-item">
                        <div class="scene-number">${sc.scene_number}</div>
                        <div class="scene-content">
                            <h4>Scene ${sc.scene_number} &mdash; ${sc.duration_seconds}s</h4>
                            <div class="scene-detail">
                                <div class="scene-field">
                                    <div class="scene-field-label">Visual Direction</div>
                                    <div class="scene-field-value">${sc.visual_description}</div>
                                </div>
                                <div class="scene-field">
                                    <div class="scene-field-label">Narration / Audio</div>
                                    <div class="scene-field-value">${sc.narration}</div>
                                </div>
                                <div class="scene-field">
                                    <div class="scene-field-label">On-Screen Text</div>
                                    <div class="scene-field-value">${sc.on_screen_text}</div>
                                </div>
                                <div class="scene-field">
                                    <div class="scene-field-label">Camera Direction</div>
                                    <div class="scene-field-value">${sc.camera_direction}</div>
                                </div>
                                <div class="image-prompt-box">
                                    <div class="scene-field-label">AI Image Generation Prompt</div>
                                    <div class="scene-field-value">${sc.image_prompt}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
    renderConstraintBadge('storyboards', constraints.storyboards);
}

/* ─── Step 6: Evaluation ───────────────────────────── */
app.runEvaluation = async function() {
    setLoading('runEvalBtn', true);
    try {
        const res = await apiCall('POST', `/api/generate/${app.campaignId}/evaluate`);
        app.state.evaluation = res.evaluation;
        app.state.metrics = { ...app.state.metrics, ...res.metrics };
        updateTime();
        renderEvaluation(res.evaluation, res.constraints, res.metrics);
        markStepCompleted('evaluation');
        app.goToStep('evaluation');
        showToast('Evaluation complete!', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('runEvalBtn', false);
};

function scoreColor(score) {
    if (score >= 8) return 'var(--success)';
    if (score >= 6) return 'var(--primary)';
    if (score >= 4) return 'var(--warning)';
    return 'var(--error)';
}

function renderEvaluation(evaluation, constraints, metrics) {
    const dash = $('#evalDashboard');
    const scores = [
        { key: 'brand_alignment', label: 'Brand Alignment' },
        { key: 'message_clarity', label: 'Message Clarity' },
        { key: 'visual_coherence', label: 'Visual Coherence' },
        { key: 'cta_effectiveness', label: 'CTA Effectiveness' },
    ];

    dash.innerHTML = `
        <div class="score-card overall">
            <div class="score-label">Overall Quality Score</div>
            <div class="score-value">${evaluation.overall_score}</div>
            <div class="score-label">out of 10.0</div>
        </div>

        ${scores.map(s => `
            <div class="score-card">
                <div class="score-label">${s.label}</div>
                <div class="score-value" style="color:${scoreColor(evaluation[s.key])}">${evaluation[s.key]}</div>
                <div class="score-bar">
                    <div class="score-bar-fill" style="width:${evaluation[s.key] * 10}%;background:${scoreColor(evaluation[s.key])}"></div>
                </div>
            </div>
        `).join('')}

        <div class="feedback-section">
            <h3>Detailed Feedback</h3>
            ${evaluation.feedback.map(f => `
                <div class="feedback-item">
                    <span class="feedback-dot"></span>
                    <span>${f}</span>
                </div>
            `).join('')}
        </div>

        <div class="constraint-summary">
            <h3>Constraint Compliance Report</h3>
            ${Object.entries(constraints).map(([stage, result]) => `
                <div class="constraint-row">
                    <span style="text-transform:capitalize">${stage}</span>
                    <span class="${result.passed ? 'constraint-pass' : 'constraint-fail'}">
                        ${result.passed ? '&#10003; PASSED' : '&#10007; FAILED'}
                        (${result.passed_rules}/${result.checked_rules} rules)
                    </span>
                </div>
                ${result.violations && result.violations.length > 0 ? `
                    <div class="violation-list">
                        ${result.violations.map(v => `
                            <div class="violation-item ${v.severity === 'warning' ? 'violation-warning' : ''}">
                                [${v.severity.toUpperCase()}] ${v.message} &mdash; ${v.location}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            `).join('')}
        </div>

        <div class="metrics-section">
            <h3>Pipeline Performance Metrics</h3>
            <div class="metrics-grid">
                ${metrics.personas_time != null ? `<div class="metric-card"><div class="metric-val">${metrics.personas_time}s</div><div class="metric-label">Personas</div></div>` : ''}
                ${metrics.angles_time != null ? `<div class="metric-card"><div class="metric-val">${metrics.angles_time}s</div><div class="metric-label">Angles</div></div>` : ''}
                ${metrics.scripts_time != null ? `<div class="metric-card"><div class="metric-val">${metrics.scripts_time}s</div><div class="metric-label">Scripts</div></div>` : ''}
                ${metrics.storyboards_time != null ? `<div class="metric-card"><div class="metric-val">${metrics.storyboards_time}s</div><div class="metric-label">Storyboards</div></div>` : ''}
                ${metrics.evaluation_time != null ? `<div class="metric-card"><div class="metric-val">${metrics.evaluation_time}s</div><div class="metric-label">Evaluation</div></div>` : ''}
                ${metrics.total_time != null ? `<div class="metric-card"><div class="metric-val">${metrics.total_time}s</div><div class="metric-label">Total TTR</div></div>` : ''}
                <div class="metric-card"><div class="metric-val">${app.apiCalls}</div><div class="metric-label">API Calls</div></div>
            </div>
        </div>
    `;
}

function renderVideoPromptOptions(prompts) {
    const options = (prompts || []).map((prompt, index) => (
        `<option value="${index}">${escapeHtml(prompt.storyboard_name || `Prompt ${index + 1}`)}</option>`
    )).join('');
    $('#videoPromptSelect').innerHTML = options;
    $('#videoEvalPromptSelect').innerHTML = options;
    renderSelectedVideoPrompt();
    renderSelectedVideoEvalPrompt();
}

function renderSelectedVideoPrompt() {
    const prompts = app.state.videoPrompts || [];
    const prompt = prompts[Number($('#videoPromptSelect').value || 0)];
    $('#videoPromptPreview').innerHTML = prompt ? `
        <div class="video-prompt-header">
            <div>
                <div class="scene-field-label">Selected Prompt</div>
                <div class="video-prompt-title">${escapeHtml(prompt.title)}</div>
            </div>
            <div class="video-prompt-chip">${(prompt.shot_plan || []).length} shots</div>
        </div>
        <div class="video-prompt-meta">
            <span class="video-prompt-pill">Storyboard: ${escapeHtml(prompt.storyboard_name || 'Untitled')}</span>
            <span class="video-prompt-pill">Prompt ready for BYOK generation</span>
        </div>
        <div class="video-prompt-copy">${escapeHtml(prompt.prompt)}</div>
        <div class="prompt-shot-list">
            <div class="scene-field-label">Shot Plan</div>
            ${(prompt.shot_plan || []).map((item, index) => `
                <div class="video-shot-item">
                    <span class="video-shot-index">${index + 1}</span>
                    <span>${escapeHtml(item)}</span>
                </div>
            `).join('')}
        </div>
    ` : `
        <div class="video-empty-state">
            <div class="video-empty-icon">+</div>
            <div>
                <div class="scene-field-label">Prompt Unavailable</div>
                <div class="scene-field-value">Generate storyboards first to unlock video prompts.</div>
            </div>
        </div>
    `;
}

function renderSelectedVideoEvalPrompt() {
    const prompts = app.state.videoPrompts || [];
    const prompt = prompts[Number($('#videoEvalPromptSelect').value || 0)];
    $('#videoEvalPromptPreview').innerHTML = prompt ? `
        <div class="video-prompt-header">
            <div>
                <div class="scene-field-label">Evaluation Target</div>
                <div class="video-prompt-title">${escapeHtml(prompt.title)}</div>
            </div>
            <div class="video-prompt-chip">${(prompt.shot_plan || []).length} shots</div>
        </div>
        <div class="video-prompt-meta">
            <span class="video-prompt-pill">Storyboard: ${escapeHtml(prompt.storyboard_name || 'Untitled')}</span>
            <span class="video-prompt-pill">Used as evaluation rubric</span>
        </div>
        <div class="video-prompt-copy">${escapeHtml(prompt.prompt)}</div>
        <div class="prompt-shot-list">
            <div class="scene-field-label">Shot Plan</div>
            ${(prompt.shot_plan || []).map((item, index) => `
                <div class="video-shot-item">
                    <span class="video-shot-index">${index + 1}</span>
                    <span>${escapeHtml(item)}</span>
                </div>
            `).join('')}
        </div>
    ` : `
        <div class="video-empty-state">
            <div class="video-empty-icon">?</div>
            <div>
                <div class="scene-field-label">Prompt Unavailable</div>
                <div class="scene-field-value">Open the video generation stage first.</div>
            </div>
        </div>
    `;
}

function renderGeneratedVideoCard() {
    const video = app.state.generatedVideo;
    const videoUrl = video?.video_url || '';
    const preview = videoUrl ? `
        <div class="generated-video-frame">
            <video controls preload="metadata" src="${escapeHtml(videoUrl)}"></video>
        </div>
    ` : '';
    $('#generatedVideoCard').innerHTML = video ? `
        <div class="generated-state-header">
            <div>
                <div class="scene-field-label">Latest Generated Video</div>
                <div class="generated-title">${escapeHtml(video.prompt_title || 'Generated output')}</div>
            </div>
            <div class="generated-status-badge">Ready</div>
        </div>
        ${preview}
        <div class="generated-meta-grid">
            <div class="generated-meta-card">
                <span class="generated-meta-label">Model</span>
                <strong>${escapeHtml(video.model || 'unknown')}</strong>
            </div>
            <div class="generated-meta-card">
                <span class="generated-meta-label">Job ID</span>
                <strong>${escapeHtml(video.provider_job_id || 'n/a')}</strong>
            </div>
            <div class="generated-meta-card">
                <span class="generated-meta-label">Render Time</span>
                <strong>${escapeHtml(String(video.time_taken ?? 'n/a'))}${video.time_taken != null ? 's' : ''}</strong>
            </div>
        </div>
        <div class="generated-link"><a href="${escapeHtml(videoUrl)}" target="_blank" rel="noreferrer">Open generated file</a></div>
    ` : `
        <div class="video-empty-state">
            <div class="video-empty-icon">&#9654;</div>
            <div>
                <div class="scene-field-label">No Render Yet</div>
                <div class="scene-field-value">Run a generation to preview the latest output here.</div>
            </div>
        </div>
    `;
}

function renderVideoEvaluationSourceCard() {
    const video = app.state.generatedVideo;
    const videoUrl = video?.video_url || '';
    $('#videoEvalSourceCard').innerHTML = video ? `
        <div class="generated-state-header">
            <div>
                <div class="scene-field-label">Latest Generated Video</div>
                <div class="generated-title">${escapeHtml(video.prompt_title || 'Generated output')}</div>
            </div>
            <div class="generated-status-badge">Ready</div>
        </div>
        <div class="generated-meta-grid">
            <div class="generated-meta-card">
                <span class="generated-meta-label">Model</span>
                <strong>${escapeHtml(video.model || 'unknown')}</strong>
            </div>
            <div class="generated-meta-card">
                <span class="generated-meta-label">Source</span>
                <strong>Generated</strong>
            </div>
        </div>
        <div class="generated-link"><a href="${escapeHtml(videoUrl)}" target="_blank" rel="noreferrer">Open generated file</a></div>
    ` : `
        <div class="video-empty-state">
            <div class="video-empty-icon">&#128279;</div>
            <div>
                <div class="scene-field-label">No Generated Video</div>
                <div class="scene-field-value">Paste a direct video URL below, or generate a video first.</div>
            </div>
        </div>
    `;
}

function scoreColorVideo(score) {
    if (score >= 8) return 'var(--success)';
    if (score >= 6) return 'var(--primary)';
    if (score >= 4) return 'var(--warning)';
    return 'var(--error)';
}

function renderVideoEvaluation(payload) {
    const evaluation = payload.evaluation;
    const sheets = payload.storyboard_sheets || [];
    $('#videoEvalDashboard').innerHTML = `
        <div class="video-eval-grid">
            <div class="score-card overall">
                <div class="score-label">Overall Video Ad Score</div>
                <div class="score-value">${evaluation.overall_score}</div>
                <div class="score-label">${escapeHtml(payload.storyboard_name || '')}</div>
            </div>
            <div class="score-card">
                <div class="score-label">Brand Alignment</div>
                <div class="score-value" style="color:${scoreColorVideo(evaluation.brand_alignment)}">${evaluation.brand_alignment}</div>
            </div>
            <div class="score-card">
                <div class="score-label">Message Clarity</div>
                <div class="score-value" style="color:${scoreColorVideo(evaluation.message_clarity)}">${evaluation.message_clarity}</div>
            </div>
            <div class="score-card">
                <div class="score-label">Visual Quality</div>
                <div class="score-value" style="color:${scoreColorVideo(evaluation.visual_quality)}">${evaluation.visual_quality}</div>
            </div>
            <div class="score-card">
                <div class="score-label">Prompt Alignment</div>
                <div class="score-value" style="color:${scoreColorVideo(evaluation.prompt_alignment)}">${evaluation.prompt_alignment}</div>
            </div>
            <div class="feedback-section">
                <h3>Overall Summary</h3>
                <div class="video-summary">${escapeHtml(evaluation.summary)}</div>
                <div class="video-segment-list">
                    ${(evaluation.segments || []).map(segment => `
                        <div class="feedback-item">
                            <span class="feedback-dot" style="background:${segment.color === 'green' ? 'var(--success)' : 'var(--error)'}"></span>
                            <span><strong>${segment.start_seconds}s-${segment.end_seconds}s · ${escapeHtml(segment.label)}</strong><br>${escapeHtml(segment.detail)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="feedback-section">
                <h3>Storyboard Contact Sheets</h3>
                <div class="storyboard-sheet-grid">
                    ${sheets.map(sheet => `
                        <div class="sheet-card">
                            <img src="${escapeHtml(sheet.image_url)}" alt="Storyboard sheet">
                            <div class="sheet-meta">Seconds: ${escapeHtml((sheet.timestamps || []).join(', '))}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;
}

app.openVideoGeneration = async function() {
    setLoading('openVideoStageBtn', true);
    try {
        const res = await apiCall('POST', `/api/generate/${app.campaignId}/video-prompts`);
        app.state.videoPrompts = res.prompts;
        app.state['video-generation'] = true;
        renderVideoPromptOptions(res.prompts);
        renderGeneratedVideoCard();
        renderVideoEvaluationSourceCard();
        markStepCompleted('video-generation');
        app.goToStep('video-generation');
        showToast('Video prompts ready.', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('openVideoStageBtn', false);
};

app.generateVideo = async function() {
    const apiKey = $('#videoApiKey').value.trim();
    if (!apiKey) return showToast('Enter an API key first', 'error');

    setLoading('generateVideoBtn', true);
    try {
        const formData = new FormData();
        formData.append('prompt_index', $('#videoPromptSelect').value || '0');
        formData.append('model', $('#videoModel').value);
        formData.append('api_key', apiKey);
        const res = await apiCallForm(`/api/generate-video/${app.campaignId}`, formData);
        app.state.generatedVideo = res;
        renderGeneratedVideoCard();
        renderVideoEvaluationSourceCard();
        showToast('Video generated.', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('generateVideoBtn', false);
};

app.copyStoryboardPrompt = async function() {
    const prompts = app.state.videoPrompts || [];
    const prompt = prompts[Number($('#videoPromptSelect').value || 0)];
    if (!prompt) return showToast('No prompt available', 'error');
    try {
        await navigator.clipboard.writeText(prompt.prompt);
        showToast('Prompt copied.', 'success');
    } catch {
        showToast('Clipboard access failed', 'error');
    }
};

app.openVideoEvaluation = async function() {
    setLoading('openVideoEvalStageBtn', true);
    try {
        if (!app.state.videoPrompts) {
            const res = await apiCall('POST', `/api/generate/${app.campaignId}/video-prompts`);
            app.state.videoPrompts = res.prompts;
        }
        app.state['video-evaluation'] = true;
        renderVideoPromptOptions(app.state.videoPrompts);
        renderGeneratedVideoCard();
        renderVideoEvaluationSourceCard();
        if (app.state.videoEvaluation) {
            renderVideoEvaluation(app.state.videoEvaluation);
        }
        app.goToStep('video-evaluation');
        showToast('Video evaluation ready.', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('openVideoEvalStageBtn', false);
};

app.evaluateGeneratedVideo = async function() {
    if (!app.state.generatedVideo?.video_url) return showToast('No generated video available', 'error');

    setLoading('evaluateGeneratedBtn', true);
    try {
        const videoUrl = app.state.generatedVideo.video_url.startsWith('/')
            ? `${window.location.origin}${app.state.generatedVideo.video_url}`
            : app.state.generatedVideo.video_url;
        const formData = new FormData();
        formData.append('prompt_index', $('#videoEvalPromptSelect').value || '0');
        formData.append('video_url', videoUrl);
        const res = await apiCallForm(`/api/evaluate-video/${app.campaignId}`, formData);
        app.state.videoEvaluation = res;
        app.state['video-evaluation'] = true;
        renderVideoEvaluationSourceCard();
        renderVideoEvaluation(res);
        markStepCompleted('video-evaluation');
        app.goToStep('video-evaluation');
        showToast('Generated video evaluated.', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('evaluateGeneratedBtn', false);
};

app.evaluateVideoUrl = async function() {
    const videoUrl = $('#videoEvalUrl').value.trim();
    if (!videoUrl) return showToast('Enter a direct video URL', 'error');

    setLoading('evaluateUrlBtn', true);
    try {
        const formData = new FormData();
        formData.append('prompt_index', $('#videoEvalPromptSelect').value || '0');
        formData.append('video_url', videoUrl);
        const res = await apiCallForm(`/api/evaluate-video/${app.campaignId}`, formData);
        app.state.videoEvaluation = res;
        app.state['video-evaluation'] = true;
        renderVideoEvaluation(res);
        markStepCompleted('video-evaluation');
        app.goToStep('video-evaluation');
        showToast('Video URL evaluated.', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
    setLoading('evaluateUrlBtn', false);
};

/* ─── Constraint Badges ────────────────────────────── */
function renderConstraintBadge(stage, result) {
    const el = $(`#constraint-${stage}`);
    if (!el || !result) return;
    if (result.passed && (!result.violations || result.violations.length === 0)) {
        el.className = 'constraint-badge pass';
        el.innerHTML = `&#10003; All ${result.checked_rules} constraint rules passed`;
    } else if (result.passed) {
        el.className = 'constraint-badge warn';
        el.innerHTML = `&#9888; Passed with ${result.violations.length} warning(s)`;
    } else {
        el.className = 'constraint-badge fail';
        el.innerHTML = `&#10007; ${result.violations.filter(v => v.severity === 'error').length} violation(s) found`;
    }
}

/* ─── Refinement Panel ─────────────────────────────── */
app.openRefinement = function(stage, index, name) {
    app.currentRefine = { stage, index };
    $('#refinementContext').textContent = `Refining: ${name} (${stage})`;
    $('#refinementInput').value = '';
    $('#refinementPanel').classList.add('open');
};

app.closeRefinement = function() {
    $('#refinementPanel').classList.remove('open');
    app.currentRefine = null;
};

app.submitRefinement = async function() {
    if (!app.currentRefine) return;
    const instruction = $('#refinementInput').value.trim();
    if (!instruction) return showToast('Enter a refinement instruction', 'error');

    const { stage, index } = app.currentRefine;
    const items = app.state[stage];
    if (!items || !items[index]) return;

    try {
        const res = await apiCall('POST', `/api/refine/${app.campaignId}`, {
            stage,
            item_index: index,
            instruction,
            current_content: JSON.stringify(items[index]),
        });
        showToast('Refinement applied!', 'success');
        app.closeRefinement();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

/* ─── Adversarial Test ─────────────────────────────── */
app.showAdversarialTest = function() {
    $('#adversarialModal').classList.add('open');
    $('#adversarialResult').innerHTML = '';
    $('#adversarialResult').className = 'test-result';
};

app.closeAdversarial = function() {
    $('#adversarialModal').classList.remove('open');
};

app.runAdversarialTest = async function() {
    const hook = $('#advHook').value;
    const value = $('#advValue').value;
    const cta = $('#advCta').value;
    if (!hook && !value && !cta) return showToast('Enter at least one test field', 'error');

    try {
        const res = await apiCall('POST', `/api/adversarial-test/${app.campaignId}`, {
            hook, value_proposition: value, cta
        });
        const el = $('#adversarialResult');
        el.className = `test-result ${res.blocked ? 'blocked' : 'passed'}`;
        el.innerHTML = `
            <strong>${res.verdict}</strong>
            ${res.violations.length > 0 ? `
                <ul style="margin-top:10px;padding-left:20px">
                    ${res.violations.map(v => `<li>[${v.severity}] ${v.rule}: ${v.message}</li>`).join('')}
                </ul>
            ` : '<p style="margin-top:8px">No policy violations detected in the test content.</p>'}
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
};

/* ─── Init ─────────────────────────────────────────── */
(async function init() {
    const bindButton = (id, handler) => {
        const el = $(id);
        if (el) el.addEventListener('click', handler);
    };
    bindButton('#generateVideoBtn', app.generateVideo);
    bindButton('#copyStoryboardPromptBtn', app.copyStoryboardPrompt);
    bindButton('#evaluateGeneratedBtn', app.evaluateGeneratedVideo);
    bindButton('#evaluateUrlBtn', app.evaluateVideoUrl);
    const videoPromptSelect = $('#videoPromptSelect');
    if (videoPromptSelect) {
        videoPromptSelect.addEventListener('change', renderSelectedVideoPrompt);
    }
    const videoEvalPromptSelect = $('#videoEvalPromptSelect');
    if (videoEvalPromptSelect) {
        videoEvalPromptSelect.addEventListener('change', renderSelectedVideoEvalPrompt);
    }
    $$('.example-preset').forEach(button => {
        button.addEventListener('click', () => applyExampleBrief(button.dataset.example));
    });
    try {
        const health = await apiCall('GET', '/health');
        if (!health.demo_mode) {
            $('#demoBadge').style.display = 'none';
        }
    } catch {
        // Server not running yet
    }
})();

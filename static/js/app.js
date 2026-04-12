/* ─── AI Ad Generator — Frontend Application ──────── */

const API = '';
const app = {
    campaignId: null,
    state: {},
    apiCalls: 0,
    currentRefine: null,
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

/* ─── Navigation ───────────────────────────────────── */
const STEPS = ['brief', 'personas', 'angles', 'scripts', 'storyboards', 'evaluation'];

app.goToStep = function(step) {
    $$('.step-panel').forEach(p => p.classList.remove('active'));
    $(`#panel-${step}`).classList.add('active');
    $$('.nav-item').forEach(n => n.classList.remove('active'));
    $(`.nav-item[data-step="${step}"]`).classList.add('active');
};

$$('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        const step = item.dataset.step;
        if (step === 'brief' || app.state[step]) {
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
    try {
        const health = await apiCall('GET', '/health');
        if (!health.demo_mode) {
            $('#demoBadge').style.display = 'none';
        }
    } catch {
        // Server not running yet
    }
})();

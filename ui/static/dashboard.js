// CenterAlign Dashboard Client Logic

let activeRunId = document.body.dataset.runId || "default_run";
let eventSource = null;

document.addEventListener("DOMContentLoaded", () => {
    initRunSelector();
    connectSSE(activeRunId);
    fetchInitialState(activeRunId);
    fetchReport(activeRunId);
});

function initRunSelector() {
    const selector = document.getElementById("run-select");
    if (!selector) return;

    fetch("/ui/runs")
        .then(res => res.json())
        .then(data => {
            selector.innerHTML = "";
            (data.runs || []).forEach(r => {
                const opt = document.createElement("option");
                opt.value = r;
                opt.textContent = r;
                if (r === activeRunId) opt.selected = true;
                selector.appendChild(opt);
            });
        });

    selector.addEventListener("change", (e) => {
        window.location.href = `/?run_id=${e.target.value}`;
    });
}

function fetchInitialState(runId) {
    fetch(`/ui/state/${runId}`)
        .then(res => res.json())
        .then(state => {
            if (state.goal) {
                document.getElementById("goal-text").textContent = state.goal;
            }
            if (state.expanded_requirements) {
                const reqList = document.getElementById("requirements-list");
                reqList.innerHTML = "";
                state.expanded_requirements.forEach(req => {
                    const li = document.createElement("li");
                    li.textContent = req;
                    reqList.appendChild(li);
                });
            }
            if (state.plan) {
                renderPlan(state.plan);
            }
        });
}

function fetchReport(runId) {
    fetch(`/ui/report/${runId}`)
        .then(res => res.json())
        .then(data => {
            const reportEl = document.getElementById("report-view");
            if (reportEl && data.report) {
                reportEl.innerHTML = marked.parse ? marked.parse(data.report) : `<pre>${data.report}</pre>`;
            }
        })
        .catch(() => {});
}

function connectSSE(runId) {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource(`/ui/events/${runId}`);

    eventSource.onmessage = (event) => {
        try {
            const ev = JSON.parse(event.data);
            handleEvent(ev);
        } catch (e) {
            console.error("Error parsing event:", e);
        }
    };
}

function handleEvent(ev) {
    const type = ev.type;
    const payload = ev.payload;

    appendActionLog(type, payload, ev.timestamp);

    if (type === "plan_created") {
        if (payload.requirements) {
            const reqList = document.getElementById("requirements-list");
            reqList.innerHTML = "";
            payload.requirements.forEach(req => {
                const li = document.createElement("li");
                li.textContent = req;
                reqList.appendChild(li);
            });
        }
        if (payload.plan) {
            renderPlan(payload.plan);
        }
    } else if (type === "step_started") {
        updateStepBadge(payload.step, "IN_PROGRESS");
    } else if (type === "step_completed") {
        updateStepBadge(payload.step, payload.filed ? "DONE" : "FAILED");
    } else if (type === "screenshot_updated") {
        updateScreenshot(payload.filepath);
    } else if (type === "approval_requested") {
        addApprovalCard(payload);
    }
}

function renderPlan(steps) {
    const planContainer = document.getElementById("plan-steps");
    if (!planContainer) return;
    planContainer.innerHTML = "";

    steps.forEach(step => {
        const div = document.createElement("div");
        div.className = "step-card";
        div.id = `step-card-${step.id}`;
        div.innerHTML = `
            <span><strong>${step.id}.</strong> ${step.description}</span>
            <span class="badge badge-${step.status.toLowerCase()}" id="badge-${step.id}">${step.status}</span>
        `;
        planContainer.appendChild(div);
    });
}

function updateStepBadge(stepId, status) {
    const badge = document.getElementById(`badge-${stepId}`);
    if (badge) {
        badge.textContent = status;
        badge.className = `badge badge-${status.toLowerCase()}`;
    }
}

function updateScreenshot(filepath) {
    const img = document.getElementById("live-screenshot-img");
    if (img && filepath) {
        // Strip reports/ if present to map to /screenshots mount
        const rel = filepath.replace(/^reports\/screenshots\//, "");
        img.src = `/screenshots/${rel}?t=${new Date().getTime()}`;
    }
}

function appendActionLog(type, payload, timestamp) {
    const logFeed = document.getElementById("action-log");
    if (!logFeed) return;

    const timeStr = timestamp ? timestamp.split("T")[1].split(".")[0] : "";
    const div = document.createElement("div");
    div.className = `log-item event-${type.includes("step") ? "step" : type.includes("approval") ? "approval" : "recovery"}`;
    div.innerHTML = `<strong>[${timeStr}] ${type}:</strong> ${JSON.stringify(payload)}`;

    logFeed.appendChild(div);
    logFeed.scrollTop = logFeed.scrollHeight;
}

function addApprovalCard(payload) {
    const queue = document.getElementById("approval-queue");
    if (!queue) return;

    const card = document.createElement("div");
    card.className = "approval-card";
    card.id = `approval-card-${payload.claim_id}`;
    card.innerHTML = `
        <h4>Approval Required: Claim #${payload.claim_id}</h4>
        <p><strong>Employee:</strong> ${payload.employee} | <strong>Amount:</strong> ₹${payload.amount_inr}</p>
        <p><strong>Vendor:</strong> ${payload.vendor} | <strong>Date:</strong> ${payload.date}</p>
        <p style="color: #f59e0b; margin-top: 0.3rem;"><strong>Reason:</strong> ${payload.reason}</p>
        <div class="btn-group">
            <button class="btn-approve" onclick="resolveApproval('${payload.claim_id}', 'APPROVED')">Approve</button>
            <button class="btn-deny" onclick="resolveApproval('${payload.claim_id}', 'DENIED')">Deny</button>
        </div>
    `;
    queue.appendChild(card);
}

function resolveApproval(claimId, decision) {
    fetch(`/ui/approval/${activeRunId}/${claimId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: decision, note: "Approved via dashboard button" })
    }).then(() => {
        const card = document.getElementById(`approval-card-${claimId}`);
        if (card) {
            card.innerHTML = `<p style="color: ${decision === 'APPROVED' ? '#10b981' : '#ef4444'};">Decision Recorded: <strong>${decision}</strong></p>`;
        }
    });
}

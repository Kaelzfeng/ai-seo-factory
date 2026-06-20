# -*- coding: utf-8 -*-
"""lib/beta_report.py · Phase 9.3.1: Beta 报告生成 (准确版)"""
import json, time

def collect_beta_metrics(tenant_id, project_id=None):
    metrics = {"tenant_id": tenant_id, "project_id": project_id}

    # Usage
    try:
        from lib.entitlements import get_tenant_entitlements
        metrics["entitlements"] = get_tenant_entitlements(tenant_id)
    except Exception: metrics["entitlements"] = {}

    # Jobs summary
    jobs_summary = {"total": 0, "completed": 0, "failed": 0,
                    "pages_success_total": 0, "pages_failed_total": 0,
                    "latest_job_id": None, "latest_job_status": None,
                    "generated_pages": 0}
    try:
        from models import list_jobs
        jobs = list_jobs(tenant_id=tenant_id)
        if project_id:
            jobs = [j for j in jobs if j.get("project_id") == project_id]
        jobs_summary["total"] = len(jobs)
        jobs_summary["completed"] = sum(1 for j in jobs if j["status"] == "completed")
        jobs_summary["failed"] = sum(1 for j in jobs if j["status"] == "failed")
        jobs_summary["pages_success_total"] = sum(j.get("pages_success", 0) for j in jobs)
        jobs_summary["pages_failed_total"] = sum(j.get("pages_failed", 0) for j in jobs)

        # Latest job
        if jobs:
            latest = jobs[0]  # list_jobs returns newest first (ORDER BY id ASC actually)
            jobs_summary["latest_job_id"] = latest["id"]
            jobs_summary["latest_job_status"] = latest["status"]

        # Generated pages from job result metadata
        for j in jobs:
            try:
                meta = json.loads(j.get("meta_json", "{}"))
                res = meta.get("_result", {})
                jobs_summary["generated_pages"] += res.get("pages_success", 0)
            except (json.JSONDecodeError, TypeError):
                pass
    except Exception:
        pass
    metrics["jobs"] = jobs_summary

    # Page contents (persisted)
    pcs_summary = {"persisted": 0, "slugs": [], "avg_quality_score": 0,
                   "review_status_counts": {}}
    try:
        from models import list_page_contents
        pcs = list_page_contents(tenant_id=tenant_id, project_id=project_id)
        pcs_summary["persisted"] = len(pcs)
        pcs_summary["slugs"] = [pc.get("slug", "") for pc in pcs[:20]]
        scores = [pc.get("quality_score", 0) for pc in pcs if pc.get("quality_score")]
        pcs_summary["avg_quality_score"] = round(sum(scores) / len(scores), 1) if scores else 0
        for pc in pcs:
            rs = pc.get("review_status", "pending")
            pcs_summary["review_status_counts"][rs] = pcs_summary["review_status_counts"].get(rs, 0) + 1
    except Exception:
        pass
    metrics["page_contents"] = pcs_summary

    # Persistence errors from job results
    persistence_errors_total = 0
    persistence_warnings_list = []
    for j in jobs:
        try:
            meta = json.loads(j.get("meta_json", "{}"))
            res = meta.get("_result", {})
            pe = res.get("persistence_errors", [])
            persistence_errors_total += len(pe)
        except (json.JSONDecodeError, TypeError):
            pass

    # Generated result summary
    note = None
    if pcs_summary["persisted"] == 0 and jobs_summary["generated_pages"] > 0:
        note = "Pages from job results but not persisted as page_contents"
    elif persistence_errors_total > 0:
        note = f"{persistence_errors_total} persistence error(s) detected — some pages generated but not saved"
    metrics["generated_pages"] = {
        "from_job_results": jobs_summary["generated_pages"],
        "note": note,
    }
    metrics["persistence_errors_count"] = persistence_errors_total

    # Competitor reports
    try:
        from models import list_competitor_reports
        reports = list_competitor_reports(tenant_id=tenant_id, project_id=project_id)
        metrics["competitor_reports"] = len(reports)
    except Exception: metrics["competitor_reports"] = 0

    # Feedback
    try:
        from lib.beta_feedback import summarize_beta_feedback
        metrics["feedback"] = summarize_beta_feedback(tenant_id, project_id)
    except Exception: metrics["feedback"] = {}

    metrics["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return metrics


def generate_private_beta_report(tenant_id, project_id=None) -> dict:
    metrics = collect_beta_metrics(tenant_id, project_id)
    return {
        "ok": True,
        "metrics": metrics,
        "known_limitations": [
            "Real WordPress publish requires wp_url/wp_username/wp_app_password",
            "Real SERP analysis requires SERP_PROVIDER configuration",
            "Real payment not integrated (mock only)",
            "Frontend is admin-only; no public website",
        ],
        "next_actions": [
            "Configure real LLM provider for production generation",
            "Set up WordPress site for publish sync",
            "Collect beta feedback from 2-5 users",
            "Run full 8-page generation with real DeepSeek/OpenAI",
        ],
    }


def beta_report_to_markdown(report: dict) -> str:
    m = report.get("metrics", {})
    e = m.get("entitlements", {})
    f = m.get("feedback", {})
    j = m.get("jobs", {})
    pc = m.get("page_contents", {})
    gp = m.get("generated_pages", {})

    lines = [
        f"# Private Beta Report",
        f"Generated: {m.get('generated_at', '')}",
        "",
        f"## Tenant {m.get('tenant_id')} (Project {m.get('project_id')})",
        f"- Plan: {e.get('plan_name', '?')} ({e.get('plan_code', '?')})",
        f"- Usage: generation={e.get('usage', {}).get('generation', 0)}/{e.get('limits', {}).get('generation', 0)}",
        "",
        "## Jobs",
        f"- Total: {j.get('total', 0)}",
        f"- Completed: {j.get('completed', 0)}",
        f"- Failed: {j.get('failed', 0)}",
        f"- Pages Success (from jobs): {j.get('pages_success_total', 0)}",
        f"- Latest Job: #{j.get('latest_job_id')} ({j.get('latest_job_status')})",
        "",
        "## Generated Pages (from job results)",
        f"- Count: {gp.get('from_job_results', 0)}",
    ]
    if gp.get("note"):
        lines.append(f"- Note: {gp['note']}")

    lines.extend([
        f"## Persistence",
        f"- Errors: {m.get('persistence_errors_count', 0)}",
    ])
    if m.get("persistence_errors_count", 0) > 0:
        lines.append("- ⚠️ Some pages were generated but NOT persisted. Check persistence_errors in job results.")

    lines.extend([
        "",
        "## Page Contents (persisted)",
        f"- Count: {pc.get('persisted', 0)}",
        f"- Avg Quality Score: {pc.get('avg_quality_score', 0)}",
        f"- Review Status: {pc.get('review_status_counts', {})}",
        f"- Slugs: {', '.join(pc.get('slugs', [])[:8])}",
        "",
        "## Competitor Reports",
        f"- Count: {m.get('competitor_reports', 0)}",
        "",
        "## Feedback",
        f"- Count: {f.get('count', 0)}",
        f"- Avg Rating: {f.get('avg_rating', 0)}",
        f"- Categories: {f.get('categories', {})}",
        "",
        "## Known Limitations",
    ])
    for lim in report.get("known_limitations", []): lines.append(f"- {lim}")
    lines.append("\n## Next Actions")
    for na in report.get("next_actions", []): lines.append(f"- {na}")
    return "\n".join(lines)

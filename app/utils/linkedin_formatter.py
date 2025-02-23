def create_linkedin_format(jobs: list) -> str:
    """Create LinkedIn post format from jobs."""
    text = "🎯 Latest Job Opportunities!\n\n"

    for job in jobs:
        text += f"🏢 {job.job_title}\n"
        if job.company_name:
            text += f"🏪 {job.company_name}\n"
        if job.job_type and job.job_type != "N/A":
            text += f"💼 {job.job_type}\n"
        if job.salary and job.salary != "N/A":
            text += f"💰 {job.salary}\n"
        if job.experience and job.experience != "N/A":
            text += f"📚 Experience: {job.experience}\n"
        text += f"🔗 Apply here: {job.apply_link}\n\n"

    text += "#jobs #careers #opportunities #hiring"
    return text

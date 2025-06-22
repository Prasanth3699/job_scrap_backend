from loguru import logger


def create_linkedin_format(jobs: list) -> str:
    """Create LinkedIn post format from jobs."""
    try:
        text = "🎯 Latest Job Opportunities!\n\n"

        for job in jobs:
            # Handle both SQLAlchemy model and dictionary
            if isinstance(job, dict):
                job_title = job.get("job_title", "N/A")
                company_name = job.get("company_name", "")
                job_type = job.get("job_type", "")
                salary = job.get("salary", "")
                experience = job.get("experience", "")
                apply_link = job.get("apply_link", "")
            else:
                job_title = job.job_title
                company_name = job.company_name
                job_type = job.job_type
                salary = job.salary
                experience = job.experience
                apply_link = job.apply_link

            text += f"🏢 {job_title}\n"
            if company_name and company_name != "N/A":
                text += f"🏪 {company_name}\n"
            if job_type and job_type != "N/A":
                text += f"💼 {job_type}\n"
            if salary and salary != "N/A":
                text += f"💰 {salary}\n"
            if experience and experience != "N/A":
                text += f"📚 Experience: {experience}\n"
            text += f"🔗 Apply here: {apply_link}\n\n"

        text += "#jobs #careers #opportunities #hiring"
        return text
    except Exception as e:
        logger.error(f"Error creating LinkedIn format: {str(e)}")
        return "Error creating job format"


# def create_linkedin_format(jobs: list) -> str:
#     """Create LinkedIn post format from jobs."""
#     text = "🎯 Latest Job Opportunities!\n\n"

#     for job in jobs:
#         text += f"🏢 {job.job_title}\n"
#         if job.company_name:
#             text += f"🏪 {job.company_name}\n"
#         if job.job_type and job.job_type != "N/A":
#             text += f"💼 {job.job_type}\n"
#         if job.salary and job.salary != "N/A":
#             text += f"💰 {job.salary}\n"
#         if job.experience and job.experience != "N/A":
#             text += f"📚 Experience: {job.experience}\n"
#         text += f"🔗 Apply here: {job.apply_link}\n\n"

#     text += "#jobs #careers #opportunities #hiring"
#     return text

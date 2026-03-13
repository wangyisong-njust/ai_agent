---
name: nus-job-applicator
description: Analyzes job descriptions against resume using WaveSpeed AI and submits Easy Apply applications
version: 1.0.0
user-invocable: true
agent: job_agent
powered_by: WaveSpeed AI
---

# NUS Job Applicator Skill

## Description
This skill automates the job application process:
1. Parses the user's resume PDF using WaveSpeed AI
2. Analyzes job description vs resume match (scored 0-100)
3. Generates a personalized cover letter via WaveSpeed AI
4. Submits LinkedIn Easy Apply or NUS TalentConnect applications via Playwright

## Trigger Phrases
- "apply to this job: [URL]"
- "analyze this JD for me"
- "help me apply to jobs"
- "check my resume match for [company]"

## Instructions
1. If resume not uploaded, ask user to upload PDF
2. Parse resume to structured JSON via WaveSpeed AI
3. Fetch job description from provided URL
4. Score JD vs resume match (WaveSpeed AI analysis)
5. If score >= 65: generate cover letter, show preview to user
6. Wait for user confirmation before submitting
7. Open browser via Playwright, fill form, submit
8. Log result to database

## Safety Rules
- ALWAYS show match score and cover letter preview BEFORE submitting
- NEVER submit without explicit user confirmation
- Rate limit: max 5 applications per session
- Skip jobs with match score < 65

## Tools Used
- resume_parser: PDF → structured JSON via WaveSpeed AI
- wavespeed_service: JD analysis + cover letter generation
- linkedin_browser: Playwright automation for Easy Apply
- job_application DB: Application tracking

## Output Format
```
📋 Job Analysis Result
Company: Grab
Role: Software Engineer Intern
Match Score: 78/100 ✅
Top Strengths: Python, ML experience, NUS background

Cover Letter Preview:
[Generated letter...]

Ready to apply? (yes/no)
```

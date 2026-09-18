const BASE = '/api/jobs'
export const fetchJobs = () => fetch(`${BASE}/list`).then(r => r.json())
export const fetchRuns = (job_id: string) => fetch(`${BASE}/runs?job_id=${job_id}`).then(r => r.json())
export const forceRun = (job_id: string) => fetch(`${BASE}/${job_id}/run`, { method: 'POST' }).then(r => r.json())
export const pauseJob = (job_id: string) => fetch(`${BASE}/${job_id}/pause`, { method: 'POST' }).then(r => r.json())
export const resumeJob = (job_id: string) => fetch(`${BASE}/${job_id}/resume`, { method: 'POST' }).then(r => r.json())

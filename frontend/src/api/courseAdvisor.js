import axios from 'axios';
import client, { CSRF_HEADER } from './client';

export function searchCourses(query) {
  return client.get('/course-advisor/search', { params: { q: query }, timeout: 30000 });
}

export function listRecommendations(semester) {
  const params = semester ? { semester } : {};
  return client.get('/course-advisor/recommendations', { params });
}

export function generateRecommendations(semester, goal = 'both', requirementBucket = null) {
  return client.post('/course-advisor/recommendations', {
    semester,
    goal,
    requirement_bucket: requirementBucket,
  }, { timeout: 60000 });
}

export function acceptRecommendation(id) {
  return client.post(`/course-advisor/recommendations/${id}/accept`);
}

export function dismissRecommendation(id) {
  return client.post(`/course-advisor/recommendations/${id}/dismiss`);
}

export function generateSemesterPlan() {
  return client.post('/course-advisor/generate-plan', {}, { timeout: 120000 });
}

/**
 * Stream a semester plan via SSE. Calls onEvent(eventObj) for each chunk.
 * Returns an AbortController so the caller can cancel.
 *
 * Event types: { type: 'summary' }, { type: 'semester', semester, index },
 *              { type: 'warnings' }, { type: 'done' }, { type: 'error' }
 */
export function streamSemesterPlan(body, onEvent) {
  const controller = new AbortController();
  const baseURL = client.defaults.baseURL || 'http://localhost:8000';

  const doFetch = () =>
    fetch(`${baseURL}/course-advisor/generate-plan/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', [CSRF_HEADER]: 'XMLHttpRequest' },
      credentials: 'include',
      body: JSON.stringify(body || {}),
      signal: controller.signal,
    });

  // Raw fetch (needed for streaming) bypasses the axios 401→refresh interceptor,
  // so replicate it: on a 401, refresh the access token once and retry, matching
  // the transparent recovery every other API call gets.
  const fetchWithRefresh = async () => {
    let response = await doFetch();
    if (response.status === 401) {
      try {
        await axios.post(
          `${baseURL}/auth/refresh`,
          {},
          { withCredentials: true, headers: { [CSRF_HEADER]: 'XMLHttpRequest' } }
        );
        response = await doFetch();
      } catch {
        // refresh failed — fall through with the original 401 response
      }
    }
    return response;
  };

  fetchWithRefresh()
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        let detail = 'Failed to generate plan.';
        try { detail = JSON.parse(text).detail || detail; } catch {}
        onEvent({ type: 'error', message: detail });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(trimmed.slice(6));
            onEvent(event);
          } catch {
            // skip malformed lines
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim().startsWith('data: ')) {
        try {
          onEvent(JSON.parse(buffer.trim().slice(6)));
        } catch {}
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onEvent({ type: 'error', message: err.message || 'Connection failed.' });
      }
    });

  return controller;
}

export function applySemesterPlan(semesters) {
  return client.post('/course-advisor/apply-plan', semesters, { timeout: 30000 });
}

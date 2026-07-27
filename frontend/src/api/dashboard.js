import client from './client';

export function getWeeklySummary() {
  return client.get('/dashboard/weekly-summary', { timeout: 30000 });
}

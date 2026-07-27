import client from './client';

export function getSchedule() {
  return client.get('/users/me/schedule');
}

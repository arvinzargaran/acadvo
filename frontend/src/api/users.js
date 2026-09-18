import client from './client';

export function getMe() {
  return client.get('/users/me');
}

export function updateUser(data) {
  return client.put('/users/me', data);
}

export function deleteAccount(password) {
  return client.delete('/users/me', { data: { password } });
}

export function changePassword(current_password, new_password) {
  return client.post('/users/me/password', { current_password, new_password });
}

export function getReadiness() {
  return client.get('/users/me/readiness');
}

export function getCalendarFeed() {
  return client.get('/users/me/calendar-feed');
}

export function regenerateCalendarFeed() {
  return client.post('/users/me/calendar-feed/regenerate');
}

/**
 * Everything the server holds about this account, as a file.
 *
 * `responseType: 'blob'` matters: the response carries a Content-Disposition
 * attachment header, and parsing it as JSON first would hold a copy of every
 * grade the account has in a JS string for no reason.
 */
export function exportMyData() {
  return client.get('/users/me/export', { responseType: 'blob' });
}

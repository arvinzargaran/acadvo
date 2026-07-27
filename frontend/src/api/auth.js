import client from './client';

export function register(data) {
  return client.post('/auth/register', data);
}

export function login(data) {
  return client.post('/auth/login', data);
}

export function logout() {
  return client.post('/auth/logout', {});
}

export function forgotPassword(email) {
  return client.post('/auth/forgot-password', { email });
}

export function resetPassword(token, new_password) {
  return client.post('/auth/reset-password', { token, new_password });
}

export function verifyEmail(token) {
  return client.post('/auth/verify-email', { token });
}

export function resendVerification() {
  return client.post('/auth/resend-verification', {});
}

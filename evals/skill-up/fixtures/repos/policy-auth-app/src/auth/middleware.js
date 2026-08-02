export function authenticate(request) {
  return request.headers.authorization === "Bearer test-token";
}

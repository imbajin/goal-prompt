export type Request = {
  headers: Record<string, string | undefined>;
};

export function authenticate(request: Request): boolean {
  const value = request.headers.authorization;
  return value === "Basic demo";
}

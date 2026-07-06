export type UserRole = "admin" | "recruiter" | "interviewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
  role: "recruiter";
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

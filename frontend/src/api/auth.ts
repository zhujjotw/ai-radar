import api from './client'

export interface LoginResponse {
  access_token: string
  token_type: string
  user: {
    username: string
    email: string
    groups: string[]
  }
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/login', { username, password })
  return data
}

export async function getMe() {
  const { data } = await api.get('/auth/me')
  return data
}

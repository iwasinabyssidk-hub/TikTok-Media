import client from './client'

export const fetchConfig = (): Promise<Record<string, unknown>> =>
  client.get<Record<string, unknown>>('/api/config').then(r => r.data)

export const saveConfig = (updates: Record<string, unknown>): Promise<Record<string, unknown>> =>
  client.put<Record<string, unknown>>('/api/config', updates).then(r => r.data)

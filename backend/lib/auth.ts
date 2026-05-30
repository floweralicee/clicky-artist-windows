import type { VercelRequest } from '@vercel/node'

import { supabaseAdmin } from './supabase'

export class HttpError extends Error {
  statusCode: number

  constructor(statusCode: number, message: string) {
    super(message)
    this.statusCode = statusCode
  }
}

export async function verifyJWT(req: VercelRequest): Promise<{ user_id: string }> {
  const authorization = req.headers.authorization
  if (!authorization?.startsWith('Bearer ')) {
    throw new HttpError(401, 'Missing auth token')
  }

  const token = authorization.slice('Bearer '.length).trim()
  const { data, error } = await supabaseAdmin.auth.getUser(token)

  if (error || !data.user) {
    throw new HttpError(401, 'Invalid auth token')
  }

  return { user_id: data.user.id }
}


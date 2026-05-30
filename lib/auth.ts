import type { VercelRequest } from '@vercel/node'
import { createClient, type SupabaseClient } from '@supabase/supabase-js'

export class HttpError extends Error {
  statusCode: number

  constructor(statusCode: number, message: string) {
    super(message)
    this.statusCode = statusCode
  }
}

let supabaseAdminClient: SupabaseClient | null = null

function getSupabaseAdmin(): SupabaseClient {
  if (supabaseAdminClient) {
    return supabaseAdminClient
  }

  const supabaseUrl = process.env.SUPABASE_URL
  const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!supabaseUrl || !supabaseServiceRoleKey) {
    throw new Error('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY')
  }

  supabaseAdminClient = createClient(supabaseUrl, supabaseServiceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  })

  return supabaseAdminClient
}

export async function verifyJWT(req: VercelRequest): Promise<{ user_id: string }> {
  const authorization = req.headers.authorization
  if (!authorization?.startsWith('Bearer ')) {
    throw new HttpError(401, 'Missing auth token')
  }

  const token = authorization.slice('Bearer '.length).trim()
  const { data, error } = await getSupabaseAdmin().auth.getUser(token)

  if (error || !data.user) {
    throw new HttpError(401, 'Invalid auth token')
  }

  return { user_id: data.user.id }
}

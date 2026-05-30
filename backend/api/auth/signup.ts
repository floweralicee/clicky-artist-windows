import type { VercelRequest, VercelResponse } from '@vercel/node'

import { supabaseAdmin } from '../../lib/supabase'

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const { email, password } = req.body ?? {}
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' })
  }

  const { data, error } = await supabaseAdmin.auth.signUp({
    email,
    password,
  })

  if (error) {
    return res.status(400).json({ error: error.message })
  }

  const jwt = data.session?.access_token
  if (!jwt) {
    return res.status(400).json({
      error: 'Account created, but no session was returned. Please sign in.',
    })
  }

  return res.status(200).json({ jwt })
}


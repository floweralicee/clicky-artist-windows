import type { VercelRequest, VercelResponse } from '@vercel/node'
import { createClient } from '@supabase/supabase-js'

const FREE_SESSION_LIMIT = 10

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const authorization = req.headers.authorization
    if (!authorization?.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Missing auth token' })
    }

    const supabaseUrl = process.env.SUPABASE_URL
    const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
    if (!supabaseUrl || !supabaseServiceRoleKey) {
      return res.status(500).json({ error: 'Supabase is not configured' })
    }

    const supabaseAdmin = createClient(supabaseUrl, supabaseServiceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    })

    const token = authorization.slice('Bearer '.length).trim()
    const { data, error } = await supabaseAdmin.auth.getUser(token)
    if (error || !data.user) {
      return res.status(401).json({ error: 'Invalid auth token' })
    }

    const userId = data.user.id

    const { count, error: usageError } = await supabaseAdmin
      .from('usage_logs')
      .select('id', { count: 'exact', head: true })
      .eq('user_id', userId)

    if (usageError) {
      return res.status(500).json({ error: `Could not count usage: ${usageError.message}` })
    }

    const { data: subscription, error: subscriptionError } = await supabaseAdmin
      .from('subscriptions')
      .select('status')
      .eq('user_id', userId)
      .order('updated_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (subscriptionError) {
      return res.status(500).json({ error: `Could not read subscription: ${subscriptionError.message}` })
    }

    const usedCount = count ?? 0
    const subscriptionStatus = subscription?.status ?? null
    const isPaid = subscriptionStatus === 'active'

    return res.status(200).json({
      subscription_status: subscriptionStatus,
      remaining_uses: Math.max(0, FREE_SESSION_LIMIT - usedCount),
      is_paid: isPaid,
      limit: FREE_SESSION_LIMIT,
      used: usedCount,
    })
  } catch {
    return res.status(500).json({ error: 'Could not check account status' })
  }
}

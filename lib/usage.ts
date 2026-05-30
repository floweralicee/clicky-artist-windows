import { createClient, type SupabaseClient } from '@supabase/supabase-js'

export type UsageStatus = {
  count: number
  limit: number
  remaining: number
  is_paid: boolean
  subscription_status: string | null
}

const FREE_SESSION_LIMIT = 10

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

export async function getUsage(user_id: string): Promise<UsageStatus> {
  const { count, error: usageError } = await getSupabaseAdmin()
    .from('usage_logs')
    .select('id', { count: 'exact', head: true })
    .eq('user_id', user_id)

  if (usageError) {
    throw new Error(`Could not count usage: ${usageError.message}`)
  }

  const { data: subscription, error: subscriptionError } = await getSupabaseAdmin()
    .from('subscriptions')
    .select('status')
    .eq('user_id', user_id)
    .order('updated_at', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (subscriptionError) {
    throw new Error(`Could not read subscription: ${subscriptionError.message}`)
  }

  const usedCount = count ?? 0
  const subscriptionStatus = subscription?.status ?? null
  const isPaid = subscriptionStatus === 'active'

  return {
    count: usedCount,
    limit: FREE_SESSION_LIMIT,
    remaining: Math.max(0, FREE_SESSION_LIMIT - usedCount),
    is_paid: isPaid,
    subscription_status: subscriptionStatus,
  }
}

export async function logUsage(user_id: string, request_type: string): Promise<void> {
  const { error } = await getSupabaseAdmin()
    .from('usage_logs')
    .insert({ user_id, request_type })

  if (error) {
    throw new Error(`Could not log usage: ${error.message}`)
  }
}

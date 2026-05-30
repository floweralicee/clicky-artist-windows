import type { VercelRequest, VercelResponse } from '@vercel/node'
import { createClient } from '@supabase/supabase-js'

const AI_GATEWAY_MODEL = 'moonshotai/kimi-k2.5'
const AI_GATEWAY_URL = 'https://ai-gateway.vercel.sh/v1/chat/completions'
const FREE_SESSION_LIMIT = 10

const SYSTEM_PROMPT = `You are an animation mentor and teacher. You help professional
animators and animation students with software including Maya, After Effects,
Blender, Toon Boom Harmony, Premiere Pro, DaVinci Resolve, and Nuke. You can
see the animator's screen. When they ask about something on screen, describe
exactly what you see and give clear, step-by-step instructions. Use animation
industry terminology correctly. Keep answers concise — animators are busy and
on deadline. When pointing at UI elements, be precise.`

type ChatContent =
  | { type: 'text'; text: string }
  | { type: 'image_url'; image_url: { url: string } }

function buildUserContent(transcript: string, screenshotBase64: string): ChatContent[] {
  const content: ChatContent[] = [{ type: 'text', text: transcript }]

  if (screenshotBase64) {
    content.push({
      type: 'image_url',
      image_url: {
        url: `data:image/jpeg;base64,${screenshotBase64}`,
      },
    })
  }

  return content
}

async function streamGatewayResponse(
  transcript: string,
  screenshotBase64: string,
  res: VercelResponse,
): Promise<void> {
  const aiGatewayApiKey = process.env.AI_GATEWAY_API_KEY
  if (!aiGatewayApiKey) {
    throw new Error('AI_GATEWAY_API_KEY is not configured')
  }

  const response = await fetch(AI_GATEWAY_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${aiGatewayApiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: AI_GATEWAY_MODEL,
      stream: true,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: buildUserContent(transcript, screenshotBase64) },
      ],
    }),
  })

  if (!response.ok || !response.body) {
    throw new Error('Vercel AI Gateway request failed')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let pending = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    pending += decoder.decode(value, { stream: true })
    const lines = pending.split('\n')
    pending = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) {
        continue
      }

      const data = trimmed.slice('data:'.length).trim()
      if (data === '[DONE]') {
        return
      }

      try {
        const parsed = JSON.parse(data)
        const chunk = parsed.choices?.[0]?.delta?.content
        if (typeof chunk === 'string' && chunk) {
          res.write(chunk)
        }
      } catch {
        // Ignore malformed SSE keepalive lines.
      }
    }
  }
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
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
    const { data, error: authError } = await supabaseAdmin.auth.getUser(token)
    if (authError || !data.user) {
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
    const remaining = Math.max(0, FREE_SESSION_LIMIT - usedCount)

    if (!isPaid && usedCount >= FREE_SESSION_LIMIT) {
      return res.status(402).json({
        error: 'paywall',
        uses: usedCount,
        limit: FREE_SESSION_LIMIT,
      })
    }

    const { transcript, screenshot_base64 } = req.body ?? {}
    if (!transcript || typeof transcript !== 'string') {
      return res.status(400).json({ error: 'Transcript is required' })
    }

    const requestType = screenshot_base64 ? 'vision' : 'text'
    const { error: logError } = await supabaseAdmin
      .from('usage_logs')
      .insert({ user_id: userId, request_type: requestType })

    if (logError) {
      return res.status(500).json({ error: `Could not log usage: ${logError.message}` })
    }

    const remainingUses = isPaid ? remaining : Math.max(0, remaining - 1)

    res.setHeader('Content-Type', 'text/plain; charset=utf-8')
    res.setHeader('Cache-Control', 'no-cache, no-transform')
    res.setHeader('X-Remaining-Uses', String(remainingUses))
    res.setHeader('X-Total-Limit', String(FREE_SESSION_LIMIT))

    await streamGatewayResponse(
      transcript,
      typeof screenshot_base64 === 'string' ? screenshot_base64 : '',
      res,
    )

    return res.end()
  } catch {
    return res.status(500).json({ error: 'Could not complete chat request' })
  }
}

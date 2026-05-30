import type { VercelRequest, VercelResponse } from '@vercel/node'

import { HttpError, verifyJWT } from '../lib/auth'
import { getUsage, logUsage } from '../lib/usage'

const AI_GATEWAY_MODEL = 'moonshotai/kimi-k2.5'
const AI_GATEWAY_URL = 'https://ai-gateway.vercel.sh/v1/chat/completions'

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
    const { user_id } = await verifyJWT(req)
    const usage = await getUsage(user_id)

    if (!usage.is_paid && usage.count >= usage.limit) {
      return res.status(402).json({
        error: 'paywall',
        uses: usage.count,
        limit: usage.limit,
      })
    }

    const { transcript, screenshot_base64 } = req.body ?? {}
    if (!transcript || typeof transcript !== 'string') {
      return res.status(400).json({ error: 'Transcript is required' })
    }

    await logUsage(user_id, screenshot_base64 ? 'vision' : 'text')

    const remainingUses = usage.is_paid
      ? usage.remaining
      : Math.max(0, usage.remaining - 1)

    res.setHeader('Content-Type', 'text/plain; charset=utf-8')
    res.setHeader('Cache-Control', 'no-cache, no-transform')
    res.setHeader('X-Remaining-Uses', String(remainingUses))
    res.setHeader('X-Total-Limit', String(usage.limit))

    await streamGatewayResponse(
      transcript,
      typeof screenshot_base64 === 'string' ? screenshot_base64 : '',
      res,
    )

    return res.end()
  } catch (error) {
    if (error instanceof HttpError) {
      return res.status(error.statusCode).json({ error: error.message })
    }
    return res.status(500).json({ error: 'Could not complete chat request' })
  }
}


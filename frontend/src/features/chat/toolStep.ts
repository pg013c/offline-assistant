import type { ChatTool } from './chatStream'

/** One line of progress for a tool call of the agent, e.g. "Reading: GDPR (EN), Art. 33". */
export function toolStep(tool: ChatTool): string {
  const args = tool.arguments
  switch (tool.name) {
    case 'search_documents':
      return typeof args.document === 'string'
        ? `Searching ${args.document}: ${text(args.query)}`
        : `Searching: ${text(args.query)}`
    case 'get_article':
      return `Reading: ${article(args)}`
    case 'compare':
      return `Comparing: ${article(args.a)} with ${article(args.b)}`
    case 'save_note':
      return `Saving note: ${text(args.title)}`
    default:
      return `Using ${tool.name}`
  }
}

function article(value: unknown): string {
  if (typeof value !== 'object' || value === null) return '?'
  const { document, number } = value as Record<string, unknown>
  return `${text(document)}, Art. ${text(number)}`
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '?'
}

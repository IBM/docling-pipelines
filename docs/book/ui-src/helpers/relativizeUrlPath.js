'use strict'

const path = require('node:path').posix

module.exports = function relativizeUrlPath (to, from) {
  if (!to) return '#'
  if (!from || typeof from !== 'string') return to
  if (to === from) return '#'

  const normalizedTo = to.startsWith('/') ? to : '/' + to
  const normalizedFrom = from.startsWith('/') ? from : '/' + from
  const fromDir = path.dirname(normalizedFrom)
  return path.relative(fromDir, normalizedTo) || '.'
}

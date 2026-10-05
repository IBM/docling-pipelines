'use strict'
module.exports = function (...args) {
  const options = args.pop()
  return args.some(Boolean)
    ? (options && options.fn ? options.fn(this) : true)
    : (options && options.inverse ? options.inverse(this) : false)
}

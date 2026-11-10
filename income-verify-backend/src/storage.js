const fs = require('fs')
const path = require('path')
const { STORAGE_DIR } = require('./config')

/**
 * Local-disk file storage under STORAGE_DIR, the same folder the ML worker reads (its storage.py).
 * Keys are relative paths; nothing outside STORAGE_DIR can be reached.
 */

const keyFor = (...parts) => parts.join('/')

function pathFor(key) {
  const full = path.resolve(STORAGE_DIR, key)
  if (!full.startsWith(STORAGE_DIR + path.sep)) throw new Error(`key escapes storage: ${key}`)
  return full
}

async function put(key, buffer) {
  const full = pathFor(key)
  await fs.promises.mkdir(path.dirname(full), { recursive: true })
  await fs.promises.writeFile(full, buffer)
  return key
}

/** Size of a stored file, or null when it is missing. */
async function stat(key) {
  try {
    return { length: (await fs.promises.stat(pathFor(key))).size }
  } catch (err) {
    if (err.code === 'ENOENT') return null
    throw err
  }
}

const openReadStream = key => fs.createReadStream(pathFor(key))

/** Delete one application's upload folder. Refuses anything that is not a single folder under uploads/. */
async function removeFolder(prefix) {
  if (!/^uploads\/[\w-]+$/.test(prefix)) throw new Error(`refusing to delete ${prefix}`)
  await fs.promises.rm(pathFor(prefix), { recursive: true, force: true })
}

module.exports = { keyFor, pathFor, put, stat, openReadStream, removeFolder }

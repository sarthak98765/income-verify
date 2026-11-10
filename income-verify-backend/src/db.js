const { Pool, types } = require('pg')
const { DATABASE_URL } = require('./config')

// numeric and bigint come back as strings by default; every amount and count here fits a JS number.
types.setTypeParser(types.builtins.NUMERIC, v => (v === null ? null : parseFloat(v)))
types.setTypeParser(types.builtins.INT8, v => (v === null ? null : parseInt(v, 10)))

const pool = new Pool({ connectionString: DATABASE_URL, max: 10 })

async function one(sql, params = []) {
  const { rows } = await pool.query(sql, params)
  return rows[0] || null
}

async function all(sql, params = []) {
  const { rows } = await pool.query(sql, params)
  return rows
}

/** Run fn(client) inside BEGIN / COMMIT, rolling back if it throws. */
async function tx(fn) {
  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    const result = await fn(client)
    await client.query('COMMIT')
    return result
  } catch (err) {
    await client.query('ROLLBACK').catch(() => {})
    throw err
  } finally {
    client.release()
  }
}

async function connect() {
  await pool.query('SELECT 1')
  console.log('[db] connected')
}

module.exports = { pool, one, all, tx, connect }

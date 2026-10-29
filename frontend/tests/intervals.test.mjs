import test from 'node:test'
import assert from 'node:assert/strict'
import { continuousInterval } from '../src/intervals.mjs'
test('seeking forward cannot produce coverage', () => assert.equal(continuousInterval(30, 90, 1, 1), null))
test('normal playback and double speed are retained', () => {
  assert.deepEqual(continuousInterval(10, 11, 1, 1), { from_seconds: 10, to_seconds: 11 })
  assert.deepEqual(continuousInterval(10, 12, 1, 2), { from_seconds: 10, to_seconds: 12 })
})
test('backwards, stalled, and non-finite intervals are ignored', () => {
  assert.equal(continuousInterval(20, 10, 1, 1), null)
  assert.equal(continuousInterval(10, 10, 1, 1), null)
  assert.equal(continuousInterval(10, Infinity, 1, 1), null)
})

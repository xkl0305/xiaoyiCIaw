#!/usr/bin/env node
/**
 * migrate_yaoyao_to_celia.mjs — 将 yaoyao 存量数据迁移到 celia 数据库
 * 先禁用 FTS 触发器，批量插入后再重建。
 */
import { createHash } from 'crypto';
import { homedir } from 'os';
import { join } from 'path';

const WORKSPACE = process.env.OPENCLAW_WORKSPACE || join(homedir(), '.openclaw/workspace');
const YAOYAO_DB = join(homedir(), '.openclaw/memory/main.sqlite');
const CELIA_DB = join(WORKSPACE, 'memory/celia_memory/celia_memory.db');

const { DatabaseSync } = await import('node:sqlite');

const TENANT_ID = 'default';
const USER_ID = 'default';
const NOW_MS = Date.now();
const stats = { meta: 0, memory_chunks: 0, session_chunks: 0, skipped: 0, errors: 0 };

function hashContent(text) {
  return createHash('sha256').update(text || '').digest('hex');
}

function insertMemRecord(db, content, occurredAtMs, memoryType = 4, category = 0, sceneTag = '') {
  const ch = hashContent(content);
  // 去重
  const existing = db.prepare(
    'SELECT id FROM mem_record WHERE content_hash = ? AND user_id = ? AND deleted_at_ms = 0 LIMIT 1'
  ).get(ch, USER_ID);
  if (existing) return false;

  db.prepare(`
    INSERT INTO mem_record 
    (tenant_id, user_id, agent_id, agent_type, session_id, scope, category, 
     memory_type, confidence, content, extract_meta, scene_tag, slot_key,
     created_at_ms, updated_at_ms, occurred_at_ms, occurred_at_source,
     content_hash, ingest_source, stable_candidate, superseded_by,
     deleted_at_ms, delete_reason, row_version, state)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    TENANT_ID, USER_ID, 'main', 'system', null, 0, category,
    memoryType, 0.5, content, null, sceneTag, null,
    NOW_MS, NOW_MS, occurredAtMs, 0,
    ch, 2, 1, null,
    0, null, 0, 0
  );
  return true;
}

try {
  const celia = new DatabaseSync(CELIA_DB);
  celia.exec('PRAGMA journal_mode=WAL');
  
  const yaoyao = new DatabaseSync(YAOYAO_DB);

  // 禁用 FTS 触发器（gspd tokenizer 在 Node sqlite3 中不可用）
  console.log('🔧 临时禁用 FTS 触发器...');
  celia.exec(`
    DROP TRIGGER IF EXISTS mem_record_fts_ai;
    DROP TRIGGER IF EXISTS mem_record_fts_ad;
    DROP TRIGGER IF EXISTS mem_record_fts_au;
  `);

  // 1. 迁移 yaoyao_meta（手动记忆）
  console.log('📋 正在迁移手动记忆...');
  const metaRows = yaoyao.prepare(`
    SELECT id, date, user_text, asst_text, importance, created_at
    FROM yaoyao_meta
    WHERE json_extract(meta, '$.superseded_by') IS NULL
      AND (user_text NOT LIKE '[ws:%' OR user_text IS NULL)
    ORDER BY id
  `).all();

  for (const row of metaRows) {
    try {
      const content = row.user_text || row.asst_text || '';
      if (!content || content.length < 10) { stats.skipped++; continue; }
      const dateStr = row.date;
      const occurredAt = dateStr ? new Date(dateStr + 'T00:00:00+08:00').getTime() : NOW_MS;
      if (insertMemRecord(celia, content, occurredAt, 4)) stats.meta++;
      else stats.skipped++;
    } catch (e) { stats.errors++; }
  }

  // 2. 迁移 chunks(source='memory')
  console.log('📋 正在迁移文件分块...');
  const memChunks = yaoyao.prepare(`
    SELECT id, path, text, start_line, end_line
    FROM chunks WHERE source = 'memory'
    ORDER BY path, start_line
  `).all();

  for (const row of memChunks) {
    try {
      const text = row.text;
      if (!text || text.length < 20) { stats.skipped++; continue; }
      const content = `[来自 ${row.path} 第${row.start_line}-${row.end_line}行]\n${text}`;
      if (insertMemRecord(celia, content, NOW_MS, 2, 2, 'workspace_file')) stats.memory_chunks++;
      else stats.skipped++;
    } catch (e) { stats.errors++; }
  }

  // 3. 迁移 chunks(source='sessions')
  console.log('📋 正在迁移会话分块...');
  const sessChunks = yaoyao.prepare(`
    SELECT id, text FROM chunks WHERE source = 'sessions' ORDER BY id
  `).all();

  for (const row of sessChunks) {
    try {
      const text = row.text;
      if (!text || text.length < 30) { stats.skipped++; continue; }
      if (insertMemRecord(celia, text, NOW_MS, 1, 1, 'conversation')) stats.session_chunks++;
      else stats.skipped++;
    } catch (e) { stats.errors++; }
  }

  // 重建 FTS 触发器
  console.log('🔧 重建 FTS 触发器...');
  celia.exec(`
    CREATE TRIGGER mem_record_fts_ai AFTER INSERT ON mem_record BEGIN
      INSERT INTO mem_record_fts(rowid, content) VALUES (new.id, new.content);
    END;
    CREATE TRIGGER mem_record_fts_ad AFTER DELETE ON mem_record BEGIN
      INSERT INTO mem_record_fts(mem_record_fts, rowid, content) VALUES ('delete', old.id, old.content);
    END;
    CREATE TRIGGER mem_record_fts_au AFTER UPDATE ON mem_record BEGIN
      INSERT INTO mem_record_fts(mem_record_fts, rowid, content) VALUES ('delete', old.id, old.content);
      INSERT INTO mem_record_fts(rowid, content) VALUES (new.id, new.content);
    END;
  `);

  celia.close();
  yaoyao.close();

  console.log(`\n✅ 迁移完成`);
  console.log(`   手动记忆: ${stats.meta} 条`);
  console.log(`   文件分块: ${stats.memory_chunks} 条`);
  console.log(`   会话分块: ${stats.session_chunks} 条`);
  console.log(`   跳过(重复/过短): ${stats.skipped} 条`);
  console.log(`   错误: ${stats.errors} 条`);
  console.log(`   总计入库: ${stats.meta + stats.memory_chunks + stats.session_chunks} 条`);

} catch (e) {
  console.error(`❌ 迁移失败: ${e.message}`);
  console.error(e.stack);
  process.exit(1);
}

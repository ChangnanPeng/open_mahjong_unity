const express = require('express');
const router = express.Router();
const pool = require('../../config/database');
const { requirePlayer } = require('../../middleware/requirePlayer');

function normalizeName(name) {
  const text = String(name || '').trim();
  if (!text) return { error: '请填写赛事名称' };
  if (text.length > 128) return { error: '赛事名称过长（最多 128 字）' };
  return { value: text };
}

function normalizeText(value, { required, label, maxLen }) {
  const text = String(value || '').trim();
  if (!text) {
    if (required) return { error: `请填写${label}` };
    return { value: '' };
  }
  if (text.length > maxLen) {
    return { error: `${label}过长（最多 ${maxLen} 字）` };
  }
  return { value: text };
}

function normalizeDate(value, { required, label }) {
  if (value === undefined || value === null || String(value).trim() === '') {
    if (required) return { error: `请填写${label}` };
    return { value: null };
  }
  const text = String(value).trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return { error: `${label}格式不正确` };
  }
  const d = new Date(`${text}T00:00:00`);
  if (Number.isNaN(d.getTime())) {
    return { error: `${label}无效` };
  }
  return { value: text };
}

router.use(requirePlayer);

router.post('/', async (req, res) => {
  try {
    const { name, description, remark, planned_start_at, planned_end_at } = req.body || {};
    const nameParsed = normalizeName(name);
    if (nameParsed.error) {
      return res.status(400).json({ success: false, message: nameParsed.error });
    }
    const startParsed = normalizeDate(planned_start_at, {
      required: true,
      label: '拟定开始时间',
    });
    if (startParsed.error) {
      return res.status(400).json({ success: false, message: startParsed.error });
    }
    const endParsed = normalizeDate(planned_end_at, {
      required: false,
      label: '拟定结束时间',
    });
    if (endParsed.error) {
      return res.status(400).json({ success: false, message: endParsed.error });
    }
    if (startParsed.value && endParsed.value && endParsed.value < startParsed.value) {
      return res.status(400).json({
        success: false,
        message: '拟定结束时间不能早于拟定开始时间',
      });
    }
    const descParsed = normalizeText(description, {
      required: true,
      label: '赛事介绍',
      maxLen: 2000,
    });
    if (descParsed.error) {
      return res.status(400).json({ success: false, message: descParsed.error });
    }
    const remarkParsed = normalizeText(remark, {
      required: false,
      label: '备注',
      maxLen: 1000,
    });
    if (remarkParsed.error) {
      return res.status(400).json({ success: false, message: remarkParsed.error });
    }

    const pending = await pool.query(
      `SELECT application_id FROM event_applications
       WHERE applicant_user_id = $1 AND status = 'pending'
       LIMIT 1`,
      [req.player.userId]
    );
    if (pending.rows.length > 0) {
      return res.status(400).json({
        success: false,
        message: '您已有一条待审核的办赛申请，请等待处理后再提交',
      });
    }

    const result = await pool.query(
      `INSERT INTO event_applications
         (applicant_user_id, name, description, remark, reason,
          planned_start_at, planned_end_at, status)
       VALUES ($1, $2, $3, $4, $3, $5, $6, 'pending')
       RETURNING application_id, applicant_user_id, name, description, remark, reason,
                 planned_start_at, planned_end_at,
                 status, event_id, created_at, updated_at, reviewed_at, review_note`,
      [
        req.player.userId,
        nameParsed.value,
        descParsed.value,
        remarkParsed.value,
        startParsed.value,
        endParsed.value,
      ]
    );

    res.json({ success: true, data: result.rows[0] });
  } catch (err) {
    if (err.code === '23505') {
      return res.status(400).json({
        success: false,
        message: '您已有一条待审核的办赛申请，请等待处理后再提交',
      });
    }
    console.error('player event-applications create:', err);
    res.status(500).json({ success: false, message: '服务器内部错误' });
  }
});

router.get('/mine', async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT application_id, applicant_user_id, name, description, remark, reason,
              planned_start_at, planned_end_at, status,
              reviewer_user_id, review_note, event_id,
              created_at, updated_at, reviewed_at
       FROM event_applications
       WHERE applicant_user_id = $1
       ORDER BY created_at DESC
       LIMIT 50`,
      [req.player.userId]
    );
    res.json({ success: true, data: { items: result.rows } });
  } catch (err) {
    console.error('player event-applications mine:', err);
    res.status(500).json({ success: false, message: '服务器内部错误' });
  }
});

module.exports = router;

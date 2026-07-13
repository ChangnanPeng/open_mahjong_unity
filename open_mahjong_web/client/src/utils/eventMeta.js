/** 赛事状态 / 角色展示文案 */

export function eventStatusLabel(status) {
  return (
    {
      registered: '已注册',
      active: '已开启',
      closed: '已关闭',
    }[status] || status || '—'
  )
}

export function eventStatusTagType(status) {
  return (
    {
      registered: 'info',
      active: 'success',
      closed: 'danger',
    }[status] || 'info'
  )
}

export function eventRoleLabel(role) {
  return role === 'owner' ? '赛事主管理员' : '赛事子管理员'
}

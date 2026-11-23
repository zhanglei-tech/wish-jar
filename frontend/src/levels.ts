// 与 backend/app/services.py 的 LEVEL_BADGE_NAMES 保持一致。
export const LEVEL_NAMES: Record<number, string> = {
  1: '初心',
  2: '初芽',
  3: '新叶',
  4: '嫩枝',
  5: '青枝',
  6: '小树',
  7: '繁叶',
  8: '含苞',
  9: '初绽',
  10: '盛放',
  11: '初果',
  12: '双果',
  13: '丰果',
  14: '晶叶',
  15: '晶枝',
  16: '晶树',
  17: '星辉',
  18: '星河',
  19: '星域',
  20: '星辉王冠',
}

export function levelBadgeName(level: number): string {
  return LEVEL_NAMES[level] ?? `Lv.${level}`
}

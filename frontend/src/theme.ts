import type { GlobalThemeOverrides } from 'naive-ui'

export const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#e86a4a',
    primaryColorHover: '#f07c5d',
    primaryColorPressed: '#c95538',
    primaryColorSuppl: '#e86a4a',
    infoColor: '#2f8f83',
    successColor: '#2f8f83',
    warningColor: '#f2b544',
    errorColor: '#d94f3d',
    textColorBase: '#3b2a20',
    textColor1: '#3b2a20',
    textColor2: '#5d4638',
    textColor3: '#8a7568',
    bodyColor: '#fff7ea',
    cardColor: '#fffdf8',
    modalColor: '#fffdf8',
    popoverColor: '#fffdf8',
    tableColor: '#fffdf8',
    inputColor: '#fffdf8',
    borderColor: '#f0e2d2',
    dividerColor: '#f0e2d2',
    borderRadius: '16px',
    borderRadiusSmall: '12px',
    fontFamily:
      '"Avenir Next", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    fontSize: '15px',
  },
  Button: {
    borderRadiusMedium: '14px',
    borderRadiusLarge: '16px',
    heightMedium: '44px',
    heightLarge: '50px',
    fontWeight: '600',
  },
  Card: {
    borderRadius: '24px',
  },
  Input: {
    borderRadius: '14px',
    heightMedium: '44px',
    heightLarge: '50px',
  },
  InputNumber: {
    borderRadius: '14px',
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: '14px',
        heightMedium: '44px',
      },
    },
  },
  Tag: {
    borderRadius: '999px',
  },
  Modal: {
    borderRadius: '24px',
  },
}

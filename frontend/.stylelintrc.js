module.exports = {
  extends: ['stylelint-config-standard', 'stylelint-config-recommended-vue'],
  // stylelint 14 默认只解析 CSS；项目样式是 less，需显式指定语法
  customSyntax: 'postcss-less',
  overrides: [
    {
      // SFC 内 <style lang="less"> 仍由 vue 语法解析，less 语法只作用于独立 .less 文件
      files: ['**/*.vue'],
      customSyntax: 'postcss-html',
    },
  ],
  defaultSeverity: 'warning',
  plugins: ['stylelint-order'],
  rules: {
    // 与 Prettier（singleQuote: true / printWidth: 80）职责重叠，交给 Prettier 执行，
    // 否则两条工具链会互相改写并产生无关 diff
    'string-quotes': null,
    'indentation': null,
    // 字体族名大小写有意义（BlinkMacSystemFont / SF Mono），不能被自动转小写
    'value-keyword-case': null,
    'at-rule-no-unknown': [
      true,
      {
        ignoreAtRules: ['plugin'],
      },
    ],
    'rule-empty-line-before': [
      'always',
      {
        except: ['after-single-line-comment', 'first-nested'],
      },
    ],
    'selector-pseudo-class-no-unknown': [
      true,
      {
        ignorePseudoClasses: ['deep'],
      },
    ],
  },
};

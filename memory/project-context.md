# 项目上下文

这里记录用户常提项目的稳定映射，供长期记忆与检索使用。

## 项目真源

- 真源文件：`ops/project_registry.json`
- 作用：统一维护项目别名、仓库地址、默认分支、工作分支约定、本地路径候选
- 原则：能从注册表命中的项目，不要再让用户重复解释“项目在哪”

## 当前已知项目

### Tower-Eye

- 正式名：`Tower-Eye`
- 用户常见叫法：`铁塔`、`铁塔项目`、`铁塔多模态检索`、`多模态检索铁塔`
- 仓库：`https://github.com/854875058/Tower-Eye`
- 默认分支：`main`
- 首选工作分支：`feat/tower-eye-review-fix`
- 本地路径候选：`/tmp/tower-eye-review-fix/repo`、`/root/projects/Tower-Eye`
- 执行约定：用户要求所有修改先落到新分支，不要直接改 `main`
- 自恢复要求：若服务器上 `gh` 已登录，但本地目录还不存在，应优先自己克隆到临时目录再工作

### Brain Secretary

- 正式名：`brain-secretary`
- 用户常见叫法：`大脑秘书`、`秘书项目`
- 仓库：`https://github.com/854875058/brain-secretary`
- 默认分支：`main`
- 本地路径：`/root/brain-secretary`

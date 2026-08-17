# SPH 远程下单助手（GitHub Actions 免费版）

手机网页下单 + GitHub Actions 免费自动下单 + 达标记录。电脑关机也能跑。

## 功能
- 📱 手机网页（GitHub Pages）：订单列表 + 新建订单（链接 + 赞/爱心/播放/转发 + 数量）
- 🤖 自动下单：在橘子平台自动登录并下单（播放/转发）
- 📊 达标检查：每 30 分钟自动抓取视频数据，达标自动标记

## 目录说明
| 目录 | 作用 |
|---|---|
| `docs/` | 手机网页（GitHub Pages 托管） |
| `remote/` | 后端：下单 + 抓取 + 订单数据 |
| `.github/workflows/` | 下单工作流 + 达标检查工作流 |
| `data/orders.json` | 订单数据（自动提交回仓库） |

## 部署步骤（一次性，约 10 分钟）

1. **新建 GitHub 仓库**（如 `sph-remote`，Public 即可）
2. **推送本项目**到该仓库（只推 `docs/ remote/ .github/ data/orders.json`，不要推本地浏览器数据）：
   ```bash
   git init
   git add docs remote .github data/orders.json
   git commit -m "init"
   git remote add origin https://github.com/<你的用户名>/sph-remote.git
   git push -u origin main
   ```
3. **配置 Secrets**（仓库 Settings → Secrets and variables → Actions → New repository secret）：
   - `JUZI_ACCOUNT`：橘子平台账号
   - `JUZI_PASSWORD`：橘子平台密码
4. **开启 GitHub Pages**（仓库 Settings → Pages → Source 选 `main` 分支 `/docs` 文件夹 → Save）
5. **手机访问** `https://<用户名>.github.io/sph-remote/`

## 使用
1. 手机打开网页，首次在「新建订单」底部填一次：GitHub 用户名 / 仓库名 / PAT
   - PAT：GitHub 个人令牌（Settings → Developer settings → Personal access tokens → 勾选 `repo` 或 `public_repo`+`issues`）
2. 粘贴视频链接，填赞/爱心/播放/转发数量，点「提交下单」
3. 网页通过 GitHub Issue 触发服务器下单（约 1-2 分钟），订单出现在「订单列表」
4. 每 30 分钟自动检查达标情况

## 下单平台
- **播放** → 橘子 商品6862（视频号-独家作品播放）
- **转发** → 橘子 商品9044（SPH-独家作品转发）
- **赞/爱心** → imt 平台（暂未接入，会提示手动下单）

## 注意事项
- 橘子账号会被视为自动下单，存在公共 IP 风控风险，请知悉
- 订单编号格式：MMDD + 当日流水（如 81701）
- 下单失败会标记为「失败」，不会自动重试

# 技術スタック選定案

## ドキュメント情報
- **作成日**: 2025-11-15
- **バージョン**: 1.0
- **目的**: Valorantチーム運営プラットフォームの技術スタック決定

---

## 推奨構成（最優先提案）

### 🎯 推奨理由
- **開発スピード**: 迅速なMVP開発が可能
- **フルスタック統合**: フロントエンド・バックエンド・認証を一元管理
- **コストパフォーマンス**: 初期段階での低コスト運用
- **スケーラビリティ**: 将来的な拡張に対応
- **開発者体験**: 優れたDX、豊富なドキュメント

---

## 1. フロントエンド

### ✅ 推奨: **Next.js 14+ (App Router) + TypeScript**

#### 選定理由
- **フルスタックフレームワーク**: API Routes統合でバックエンド不要
- **SSR/SSG対応**: SEOとパフォーマンス最適化
- **ファイルベースルーティング**: 直感的な開発体験
- **React Server Components**: 最新のReact機能活用
- **Vercelデプロイ最適化**: ワンクリックデプロイ
- **TypeScript完全サポート**: 型安全性

#### 技術詳細
```json
{
  "framework": "Next.js 15.0+",
  "language": "TypeScript 5.3+",
  "runtime": "Node.js 20+",
  "package-manager": "pnpm"
}
```

#### 主要ライブラリ
```json
{
  "ui": "shadcn/ui + Radix UI + Tailwind CSS",
  "state-management": "Zustand / Jotai",
  "forms": "React Hook Form + Zod",
  "data-fetching": "TanStack Query (React Query)",
  "charts": "Recharts / Chart.js",
  "calendar": "FullCalendar / react-big-calendar",
  "image-upload": "react-dropzone",
  "notifications": "react-hot-toast / sonner",
  "icons": "lucide-react"
}
```

### 代替案1: React + Vite
- より軽量、学習コストが低い
- バックエンドを別途構築する必要がある
- SSRが不要な場合は選択肢

### 代替案2: Vue 3 + Nuxt 3
- Vue生態系を選好する場合
- Composition API、優れたDX

---

## 2. バックエンド

### ✅ 推奨: **Next.js API Routes (フルスタック構成)**

#### 選定理由
- フロントエンドと同一コードベース
- サーバーレス関数として動作
- Vercelで自動スケーリング
- Middlewareによる認証・バリデーション

#### API構成
```
/app/api/
├── auth/
│   ├── [...nextauth]/route.ts  # NextAuth.js
│   └── discord/route.ts
├── teams/
│   ├── route.ts                # GET, POST /api/teams
│   ├── [teamId]/route.ts       # GET, PUT, DELETE /api/teams/:id
│   └── [teamId]/members/route.ts
├── matches/
│   ├── route.ts
│   ├── [matchId]/route.ts
│   └── upload/route.ts         # スクリーンショットアップロード
├── goals/route.ts
├── schedules/route.ts
├── feedback/route.ts
├── conditions/route.ts
└── ocr/route.ts                # DeepSeek OCR統合
```

### 代替案: 独立したバックエンド
もしマイクロサービス化や独立したAPIサーバーが必要な場合:

**Node.js + Express + TypeScript**
```json
{
  "framework": "Express.js",
  "validation": "Zod / Joi",
  "auth": "Passport.js",
  "orm": "Prisma"
}
```

**Python + FastAPI**
```python
# OCR処理が重い場合、Python非同期処理が有利
{
  "framework": "FastAPI",
  "validation": "Pydantic",
  "orm": "SQLAlchemy / Tortoise ORM"
}
```

---

## 3. データベース

### ✅ 推奨: **Supabase (PostgreSQL + Auth + Storage)**

#### 選定理由
- **オールインワン**: DB + 認証 + ストレージ + Realtime
- **PostgreSQL**: リレーショナルDB、高性能
- **Row Level Security**: 高度なアクセス制御
- **無料枠**: 500MB DB、1GB Storage
- **Discord OAuth統合**: ビルトインサポート
- **TypeScript SDK**: 型安全なクライアント
- **自動API生成**: RESTful + GraphQL

#### スキーマ設計（Prisma風）
```prisma
// Supabaseはネイティブで以下のテーブルを生成
model User {
  id            String   @id @default(uuid())
  discordId     String   @unique
  username      String
  avatar        String?
  createdAt     DateTime @default(now())

  teamMembers   TeamMember[]
  conditions    Condition[]
  feedbacks     Feedback[]
}

model Team {
  id            String   @id @default(uuid())
  name          String
  tag           String
  logo          String?
  description   String?
  isPublic      Boolean  @default(false)
  createdAt     DateTime @default(now())

  members       TeamMember[]
  matches       Match[]
  goals         Goal[]
  schedules     Schedule[]
}

model TeamMember {
  id            String   @id @default(uuid())
  teamId        String
  userId        String
  role          Role     @default(PLAYER)
  joinedAt      DateTime @default(now())

  team          Team     @relation(fields: [teamId])
  user          User     @relation(fields: [userId])

  @@unique([teamId, userId])
}

enum Role {
  OWNER
  MANAGER
  COACH
  PLAYER
  SUB
}

model Player {
  id            String   @id @default(uuid())
  userId        String   @unique
  inGameNames   String[] // JSONB array
  mainAgents    String[]
  playStyle     String?

  // スキル評価
  mechanicsScore    Int @default(3)
  aimScore          Int @default(3)
  characterScore    Int @default(3)
  teamworkScore     Int @default(3)
  mapScore          Int @default(3)

  user          User     @relation(fields: [userId])
  matchPlayers  MatchPlayer[]
}

model Match {
  id            String   @id @default(uuid())
  teamId        String
  matchDate     DateTime
  matchType     MatchType @default(SCRIM)
  mapName       String
  isWin         Boolean
  teamScore     Int
  enemyScore    Int
  enemyTeamName String?
  screenshotUrl String?
  createdAt     DateTime @default(now())

  team          Team     @relation(fields: [teamId])
  players       MatchPlayer[]
  feedbacks     Feedback[]
}

enum MatchType {
  SCRIM
  RANKED
  TOURNAMENT
  CUSTOM
}

model MatchPlayer {
  id            String   @id @default(uuid())
  matchId       String
  playerId      String
  inGameName    String
  agent         String
  acs           Int
  kills         Int
  deaths        Int
  assists       Int
  firstBloods   Int      @default(0)
  plants        Int      @default(0)
  defuses       Int      @default(0)

  match         Match    @relation(fields: [matchId])
  player        Player   @relation(fields: [playerId])

  @@unique([matchId, playerId])
}

model Goal {
  id            String   @id @default(uuid())
  teamId        String?
  userId        String?  // 個人目標の場合
  type          GoalType
  title         String
  description   String?
  deadline      DateTime?
  progress      Int      @default(0) // 0-100
  status        GoalStatus @default(IN_PROGRESS)
  createdAt     DateTime @default(now())

  team          Team?    @relation(fields: [teamId])
  user          User?    @relation(fields: [userId])
  feedbacks     Feedback[]
}

enum GoalType {
  TEAM_LONG
  TEAM_MEDIUM
  TEAM_SHORT
  PERSONAL
}

enum GoalStatus {
  IN_PROGRESS
  ACHIEVED
  FAILED
  PENDING
}

model DailyRule {
  id            String   @id @default(uuid())
  teamId        String
  type          RuleType
  title         String
  description   String?
  isActive      Boolean  @default(true)

  team          Team     @relation(fields: [teamId])
}

enum RuleType {
  DO
  DONT
}

model Condition {
  id            String   @id @default(uuid())
  userId        String
  date          DateTime @db.Date
  physicalScore Int      // 1-5
  mentalScore   Int      // 1-5
  motivationScore Int    // 1-5
  sleepHours    Float?
  comment       String?

  user          User     @relation(fields: [userId])

  @@unique([userId, date])
}

model Schedule {
  id            String   @id @default(uuid())
  teamId        String
  type          ScheduleType
  title         String
  description   String?
  startTime     DateTime
  endTime       DateTime
  isRecurring   Boolean  @default(false)
  recurringRule String?  // JSON: rrule format
  createdBy     String

  team          Team     @relation(fields: [teamId])
  attendances   Attendance[]
}

enum ScheduleType {
  TEAM_PRACTICE
  SCRIM
  PERSONAL_PRACTICE
  MEETING
}

model Attendance {
  id            String   @id @default(uuid())
  scheduleId    String
  userId        String
  status        AttendanceStatus @default(PENDING)
  reason        String?

  schedule      Schedule @relation(fields: [scheduleId])
  user          User     @relation(fields: [userId])

  @@unique([scheduleId, userId])
}

enum AttendanceStatus {
  ATTENDING
  ABSENT
  PENDING
}

model Feedback {
  id            String   @id @default(uuid())
  authorId      String
  targetType    FeedbackTarget
  targetId      String   // matchId, goalId, userId
  content       String
  rating        Int?     // 1-5 (optional)
  createdAt     DateTime @default(now())

  author        User     @relation(fields: [authorId])
}

enum FeedbackTarget {
  MATCH_TEAM
  MATCH_PLAYER
  GOAL
  PLAYER
}
```

### 代替案1: PostgreSQL + Prisma
- より細かいコントロールが必要な場合
- Supabase以外のホスティング（AWS RDS、Railway等）

### 代替案2: MongoDB + Mongoose
- スキーマレスな柔軟性が必要な場合
- ドキュメント指向のデータ構造

---

## 4. 認証

### ✅ 推奨: **NextAuth.js v5 (Auth.js) + Discord Provider**

#### 設定例
```typescript
// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth"
import DiscordProvider from "next-auth/providers/discord"
import { SupabaseAdapter } from "@auth/supabase-adapter"

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    DiscordProvider({
      clientId: process.env.DISCORD_CLIENT_ID!,
      clientSecret: process.env.DISCORD_CLIENT_SECRET!,
      authorization: {
        params: {
          scope: "identify email guilds"
        }
      }
    })
  ],
  adapter: SupabaseAdapter({
    url: process.env.NEXT_PUBLIC_SUPABASE_URL!,
    secret: process.env.SUPABASE_SERVICE_ROLE_KEY!
  }),
  callbacks: {
    session({ session, user }) {
      session.user.id = user.id
      return session
    }
  }
})
```

#### Discord OAuth設定
1. Discord Developer Portal でアプリケーション作成
2. OAuth2 Redirect URL: `https://yourdomain.com/api/auth/callback/discord`
3. Scopes: `identify`, `email`, `guilds`

---

## 5. ファイルストレージ

### ✅ 推奨: **Supabase Storage**

#### 選定理由
- Supabaseと統合済み
- CDN自動配信
- 画像リサイズ・変換機能
- Row Level Security
- 無料枠: 1GB

#### バケット構成
```
valo-platform/
├── avatars/          # ユーザーアバター
├── team-logos/       # チームロゴ
├── match-screenshots/# 試合結果スクショ
└── temp/             # 一時ファイル
```

#### アップロード例
```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(url, key)

async function uploadScreenshot(file: File, matchId: string) {
  const filePath = `match-screenshots/${matchId}/${Date.now()}.png`

  const { data, error } = await supabase.storage
    .from('valo-platform')
    .upload(filePath, file, {
      cacheControl: '3600',
      upsert: false
    })

  if (error) throw error

  const { data: { publicUrl } } = supabase.storage
    .from('valo-platform')
    .getPublicUrl(filePath)

  return publicUrl
}
```

### 代替案: Cloudflare R2
- S3互換、低コスト（egress無料）
- グローバルCDN

---

## 6. OCR処理

### ✅ 推奨: **DeepSeek OCR API + ファイルアップロード処理**

#### 処理フロー
```typescript
// app/api/ocr/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const formData = await req.formData()
  const file = formData.get('screenshot') as File

  // 1. Supabase Storageにアップロード
  const filePath = await uploadToStorage(file)

  // 2. DeepSeek OCRで解析
  const ocrResult = await analyzeWithDeepSeek(filePath)

  // 3. 結果をパース
  const matchData = parseOCRResult(ocrResult)

  // 4. IGNマッピング
  const mappedPlayers = await mapInGameNames(matchData.players)

  return NextResponse.json({
    success: true,
    data: {
      ...matchData,
      players: mappedPlayers
    }
  })
}

async function analyzeWithDeepSeek(imageUrl: string) {
  const response = await fetch('https://api.deepseek.com/v1/ocr', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      image_url: imageUrl,
      language: 'ja',
      output_format: 'json'
    })
  })

  return response.json()
}

function parseOCRResult(ocrData: any) {
  // OCR結果から構造化データを抽出
  // マップ名、スコア、プレイヤー統計などをパース
  return {
    map: extractMap(ocrData),
    score: extractScore(ocrData),
    players: extractPlayers(ocrData)
  }
}
```

#### エラーハンドリング
- OCR失敗時は手動入力フォームを表示
- 信頼度スコアが低い項目はハイライト表示

---

## 7. 通知システム

### ✅ 推奨: **Discord Webhooks**

#### 実装例
```typescript
// lib/discord-webhook.ts
export async function sendDiscordNotification(
  webhookUrl: string,
  message: {
    title: string
    description: string
    color?: number
    fields?: Array<{ name: string; value: string; inline?: boolean }>
  }
) {
  await fetch(webhookUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      embeds: [{
        title: message.title,
        description: message.description,
        color: message.color || 0xFF4655, // Valorant red
        fields: message.fields,
        timestamp: new Date().toISOString()
      }]
    })
  })
}

// 使用例: スケジュール通知
await sendDiscordNotification(team.webhookUrl, {
  title: '🎯 スクリム開始1時間前',
  description: '対戦相手: Team Alpha',
  fields: [
    { name: '時間', value: '20:00', inline: true },
    { name: 'マップ', value: 'Haven, Bind', inline: true }
  ]
})
```

#### チームごとのWebhook設定
```typescript
model Team {
  // ...
  discordWebhookUrl String?
  notificationSettings Json? // { schedule: true, match: true, goal: false }
}
```

---

## 8. UI/UXライブラリ

### ✅ 推奨: **shadcn/ui + Tailwind CSS**

#### 選定理由
- コンポーネントコピー方式（依存関係なし）
- カスタマイズ自由度が高い
- Radix UI基盤で accessibility良好
- ダークモード完全サポート

#### セットアップ
```bash
pnpm dlx shadcn-ui@latest init
pnpm dlx shadcn-ui@latest add button card input form table
```

#### カスタムテーマ（Valorant風）
```typescript
// tailwind.config.ts
export default {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        valo: {
          red: '#FF4655',
          dark: '#0F1923',
          darker: '#0A0E14',
          light: '#ECE8E1'
        }
      }
    }
  }
}
```

### 追加UIライブラリ
- **フォーム**: React Hook Form + Zod
- **テーブル**: TanStack Table
- **カレンダー**: react-big-calendar
- **グラフ**: Recharts
- **アニメーション**: Framer Motion

---

## 9. 状態管理

### ✅ 推奨: **TanStack Query + Zustand**

#### TanStack Query (React Query)
サーバー状態管理
```typescript
// hooks/useTeam.ts
import { useQuery } from '@tanstack/react-query'

export function useTeam(teamId: string) {
  return useQuery({
    queryKey: ['team', teamId],
    queryFn: () => fetch(`/api/teams/${teamId}`).then(r => r.json()),
    staleTime: 5 * 60 * 1000 // 5分
  })
}
```

#### Zustand
グローバルクライアント状態
```typescript
// store/ui-store.ts
import { create } from 'zustand'

interface UIStore {
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  toggleTheme: () => void
  toggleSidebar: () => void
}

export const useUIStore = create<UIStore>((set) => ({
  theme: 'dark',
  sidebarOpen: true,
  toggleTheme: () => set((state) => ({
    theme: state.theme === 'dark' ? 'light' : 'dark'
  })),
  toggleSidebar: () => set((state) => ({
    sidebarOpen: !state.sidebarOpen
  }))
}))
```

---

## 10. デプロイ・ホスティング

### ✅ 推奨: **Vercel (Next.js) + Supabase**

#### Vercel
- Next.js最適化
- 自動CI/CD（Gitプッシュで自動デプロイ）
- Edge Functions
- 無料枠: 100GB帯域、1000時間関数実行

#### 環境変数設定
```bash
# Vercel Environment Variables
NEXT_PUBLIC_SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DEEPSEEK_API_KEY=
NEXTAUTH_SECRET=
NEXTAUTH_URL=
```

#### デプロイコマンド
```bash
# Vercelにデプロイ
pnpm vercel

# 本番環境
pnpm vercel --prod
```

### 代替案
- **Railway**: バックエンド + DB統合ホスティング
- **Render**: 無料Postgres、自動スケーリング
- **AWS Amplify**: AWS生態系統合

---

## 11. 開発ツール

### リンター・フォーマッター
```json
{
  "devDependencies": {
    "eslint": "^8.x",
    "eslint-config-next": "^14.x",
    "prettier": "^3.x",
    "prettier-plugin-tailwindcss": "^0.5.x",
    "@typescript-eslint/parser": "^6.x",
    "@typescript-eslint/eslint-plugin": "^6.x"
  }
}
```

### Git Hooks
```bash
pnpm add -D husky lint-staged

# .husky/pre-commit
pnpm lint-staged
```

### テスト
```json
{
  "devDependencies": {
    "vitest": "^1.x",
    "@testing-library/react": "^14.x",
    "@testing-library/jest-dom": "^6.x",
    "playwright": "^1.x"
  }
}
```

---

## 12. 開発環境構築

### 必須ソフトウェア
- **Node.js**: v20.x LTS
- **pnpm**: v8.x
- **Git**: 最新版
- **VSCode**: 推奨エディタ

### VSCode拡張機能
```json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "Prisma.prisma",
    "ms-vscode.vscode-typescript-next"
  ]
}
```

### 環境セットアップ
```bash
# リポジトリクローン
git clone <repository-url>
cd valo-platform

# 依存関係インストール
pnpm install

# 環境変数設定
cp .env.example .env.local
# .env.localを編集

# Supabase初期化
pnpm supabase init
pnpm supabase db push

# 開発サーバー起動
pnpm dev
```

---

## 13. コスト試算

### 初期段階（100ユーザー想定）

| サービス | プラン | 月額コスト |
|---------|--------|----------|
| Vercel | Hobby | $0 |
| Supabase | Free | $0 |
| DeepSeek OCR | Pay-as-you-go | ~$10 |
| ドメイン | - | ~$1 |
| **合計** | | **~$11/月** |

### 成長期（1000ユーザー想定）

| サービス | プラン | 月額コスト |
|---------|--------|----------|
| Vercel | Pro | $20 |
| Supabase | Pro | $25 |
| DeepSeek OCR | - | ~$50 |
| CDN/Storage | - | ~$10 |
| **合計** | | **~$105/月** |

---

## 14. まとめ

### 推奨構成一覧

| カテゴリ | 技術 |
|---------|------|
| **フロントエンド** | Next.js 14+ + TypeScript |
| **UI** | shadcn/ui + Tailwind CSS |
| **バックエンド** | Next.js API Routes |
| **データベース** | Supabase (PostgreSQL) |
| **認証** | NextAuth.js + Discord OAuth |
| **ストレージ** | Supabase Storage |
| **OCR** | DeepSeek OCR API |
| **通知** | Discord Webhooks |
| **状態管理** | TanStack Query + Zustand |
| **デプロイ** | Vercel |
| **パッケージ管理** | pnpm |

### 開発開始手順
1. ✅ この技術スタックで承認を得る
2. ⬜ Supabaseプロジェクト作成
3. ⬜ Discord Appアプリケーション登録
4. ⬜ DeepSeek APIキー取得
5. ⬜ Next.jsプロジェクト初期化
6. ⬜ Supabaseスキーマ作成
7. ⬜ 認証フロー実装
8. ⬜ MVP Phase 1 開発開始

---

## 15. 代替案検討

もし上記構成が合わない場合の代替案：

### フルスタック代替
- **T3 Stack**: Next.js + tRPC + Prisma + NextAuth
- **Remix**: React Router v7、優れたフォーム処理

### バックエンド分離構成
- **Frontend**: React + Vite
- **Backend**: Node.js + Express + Prisma
- **Deploy**: Frontend (Vercel), Backend (Railway)

### モノリス構成
- **Ruby on Rails**: 迅速な開発、convention over configuration
- **Django**: Python、管理画面自動生成

---

**次のステップ**: この技術スタックで問題なければ、データベーススキーマとAPI設計に進みます。

# データベース設計書

## ドキュメント情報
- **作成日**: 2025-11-15
- **バージョン**: 1.0
- **DBMS**: PostgreSQL (Supabase)
- **ORM**: Prisma / Supabase Client

---

## 1. ER図（概念モデル）

```
┌─────────────┐
│    User     │
└──────┬──────┘
       │
       │ 1:N
       ▼
┌─────────────┐     1:N      ┌─────────────┐
│ TeamMember  ├─────────────►│    Team     │
└──────┬──────┘              └──────┬──────┘
       │                            │
       │                            │ 1:N
       │                            ▼
       │                     ┌─────────────┐
       │                     │   Match     │
       │                     └──────┬──────┘
       │                            │
       │                            │ 1:N
       │                            ▼
       │                     ┌─────────────┐
       │                     │MatchPlayer │◄─────┐
       │                     └─────────────┘      │
       │                                          │
       │ 1:1                                      │ N:1
       ▼                                          │
┌─────────────┐                                  │
│   Player    ├──────────────────────────────────┘
└──────┬──────┘
       │
       │ 1:N
       ▼
┌─────────────┐
│ Condition   │
└─────────────┘

      User
       │
       │ 1:N
       ▼
┌─────────────┐     N:1      ┌─────────────┐
│  Feedback   ├─────────────►│  (Target)   │
└─────────────┘              └─────────────┘
                             (Match, Goal, Player)

      Team
       │
       │ 1:N
       ├─────────────┬────────────┬─────────────┐
       ▼             ▼            ▼             ▼
┌─────────┐   ┌──────────┐  ┌─────────┐  ┌──────────┐
│  Goal   │   │ Schedule │  │DailyRule│  │Attendance│
└─────────┘   └──────────┘  └─────────┘  └──────────┘
```

---

## 2. テーブル定義

### 2.1 User（ユーザー）

**説明**: Discord認証ユーザーの基本情報

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | ユーザーID |
| discord_id | VARCHAR(255) | UNIQUE, NOT NULL | Discord Snowflake ID |
| username | VARCHAR(100) | NOT NULL | Discord表示名 |
| discriminator | VARCHAR(10) | | Discord#タグ (deprecated) |
| avatar_url | TEXT | | Discordアバター画像URL |
| email | VARCHAR(255) | UNIQUE | メールアドレス |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**インデックス**:
- `idx_user_discord_id` ON (discord_id)
- `idx_user_email` ON (email)

---

### 2.2 Team（チーム）

**説明**: Valorantチーム情報

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | チームID |
| name | VARCHAR(100) | NOT NULL | チーム名 |
| tag | VARCHAR(10) | NOT NULL | チームタグ (例: VLR) |
| logo_url | TEXT | | チームロゴ画像URL |
| description | TEXT | | チーム説明 |
| is_public | BOOLEAN | DEFAULT FALSE | 公開/非公開 |
| discord_webhook_url | TEXT | | Discord通知用WebhookURL |
| notification_settings | JSONB | | 通知設定 |
| created_by | UUID | FK → User(id) | 作成者 |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**通知設定 JSON例**:
```json
{
  "schedule": true,
  "match": true,
  "goal": false,
  "feedback": true
}
```

**インデックス**:
- `idx_team_created_by` ON (created_by)
- `idx_team_tag` ON (tag)

---

### 2.3 TeamMember（チームメンバー）

**説明**: ユーザーとチームの関連、ロール管理

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | メンバーID |
| team_id | UUID | FK → Team(id), NOT NULL | チームID |
| user_id | UUID | FK → User(id), NOT NULL | ユーザーID |
| role | ENUM | NOT NULL | ロール |
| joined_at | TIMESTAMP | DEFAULT NOW() | 加入日時 |
| left_at | TIMESTAMP | | 脱退日時 |
| is_active | BOOLEAN | DEFAULT TRUE | 現在所属中か |

**ENUM: Role**
- `OWNER` - チームオーナー
- `MANAGER` - マネージャー
- `COACH` - コーチ
- `PLAYER` - プレイヤー
- `SUB` - サブメンバー

**制約**:
- UNIQUE(team_id, user_id) WHERE is_active = TRUE

**インデックス**:
- `idx_team_member_team` ON (team_id)
- `idx_team_member_user` ON (user_id)
- `idx_team_member_role` ON (role)

---

### 2.4 Player（選手プロフィール）

**説明**: 選手の詳細情報とスキル評価

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | 選手ID |
| user_id | UUID | FK → User(id), UNIQUE | ユーザーID |
| in_game_names | JSONB | DEFAULT '[]' | IGN一覧 |
| main_agents | TEXT[] | | 得意エージェント |
| play_style | TEXT | | プレイスタイル説明 |
| mechanics_score | INTEGER | DEFAULT 3, CHECK(1-5) | メカニクス評価 |
| aim_score | INTEGER | DEFAULT 3, CHECK(1-5) | エイム評価 |
| character_score | INTEGER | DEFAULT 3, CHECK(1-5) | キャラ理解評価 |
| teamwork_score | INTEGER | DEFAULT 3, CHECK(1-5) | チーム理解評価 |
| map_score | INTEGER | DEFAULT 3, CHECK(1-5) | マップ理解評価 |
| last_evaluated_at | TIMESTAMP | | 最終評価日時 |
| evaluated_by | UUID | FK → User(id) | 評価者 |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**IGN JSONB例**:
```json
[
  { "name": "PlayerName#001", "isPrimary": true },
  { "name": "SubAccount#002", "isPrimary": false }
]
```

**インデックス**:
- `idx_player_user` ON (user_id)
- `idx_player_ign` ON ((in_game_names)) USING GIN

---

### 2.5 Match（試合記録）

**説明**: チームの試合結果

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | 試合ID |
| team_id | UUID | FK → Team(id), NOT NULL | チームID |
| match_date | TIMESTAMP | NOT NULL | 試合日時 |
| match_type | ENUM | NOT NULL | 試合種類 |
| map_name | VARCHAR(50) | NOT NULL | マップ名 |
| is_win | BOOLEAN | NOT NULL | 勝敗 (TRUE=勝利) |
| team_score | INTEGER | NOT NULL | 自チームスコア |
| enemy_score | INTEGER | NOT NULL | 敵チームスコア |
| enemy_team_name | VARCHAR(100) | | 対戦相手チーム名 |
| screenshot_url | TEXT | | リザルトスクショURL |
| ocr_raw_data | JSONB | | OCR生データ |
| notes | TEXT | | メモ |
| created_by | UUID | FK → User(id) | 登録者 |
| created_at | TIMESTAMP | DEFAULT NOW() | 登録日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**ENUM: MatchType**
- `SCRIM` - スクリム
- `RANKED` - ランクマッチ
- `TOURNAMENT` - 大会
- `CUSTOM` - カスタム

**インデックス**:
- `idx_match_team_date` ON (team_id, match_date DESC)
- `idx_match_type` ON (match_type)
- `idx_match_map` ON (map_name)

---

### 2.6 MatchPlayer（試合参加者統計）

**説明**: 各試合における選手の個別統計

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | レコードID |
| match_id | UUID | FK → Match(id), NOT NULL | 試合ID |
| player_id | UUID | FK → Player(id), NOT NULL | 選手ID |
| in_game_name | VARCHAR(100) | NOT NULL | 使用したIGN |
| agent | VARCHAR(50) | NOT NULL | 使用エージェント |
| acs | INTEGER | NOT NULL | Average Combat Score |
| kills | INTEGER | NOT NULL | キル数 |
| deaths | INTEGER | NOT NULL | デス数 |
| assists | INTEGER | NOT NULL | アシスト数 |
| first_bloods | INTEGER | DEFAULT 0 | ファーストブラッド数 |
| plants | INTEGER | DEFAULT 0 | スパイク設置数 |
| defuses | INTEGER | DEFAULT 0 | スパイク解除数 |
| headshot_percentage | DECIMAL(5,2) | | ヘッドショット率 |
| damage_per_round | INTEGER | | ラウンド平均ダメージ |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |

**制約**:
- UNIQUE(match_id, player_id)

**計算フィールド**:
- `kd_ratio`: kills::DECIMAL / NULLIF(deaths, 0)
- `kda`: (kills + assists) / NULLIF(deaths, 0)

**インデックス**:
- `idx_match_player_match` ON (match_id)
- `idx_match_player_player` ON (player_id)
- `idx_match_player_ign` ON (in_game_name)

---

### 2.7 Goal（目標）

**説明**: チームまたは個人の目標

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | 目標ID |
| team_id | UUID | FK → Team(id) | チームID (チーム目標の場合) |
| user_id | UUID | FK → User(id) | ユーザーID (個人目標の場合) |
| type | ENUM | NOT NULL | 目標タイプ |
| title | VARCHAR(200) | NOT NULL | 目標タイトル |
| description | TEXT | | 詳細説明 |
| deadline | DATE | | 達成期限 |
| progress | INTEGER | DEFAULT 0, CHECK(0-100) | 進捗率(%) |
| status | ENUM | DEFAULT 'IN_PROGRESS' | ステータス |
| created_by | UUID | FK → User(id) | 作成者 |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**ENUM: GoalType**
- `TEAM_LONG` - チーム長期目標
- `TEAM_MEDIUM` - チーム中期目標
- `TEAM_SHORT` - チーム短期目標
- `PERSONAL` - 個人目標

**ENUM: GoalStatus**
- `IN_PROGRESS` - 進行中
- `ACHIEVED` - 達成
- `FAILED` - 未達成
- `PENDING` - 保留

**制約**:
- CHECK((team_id IS NOT NULL AND user_id IS NULL) OR (team_id IS NULL AND user_id IS NOT NULL))

**インデックス**:
- `idx_goal_team` ON (team_id)
- `idx_goal_user` ON (user_id)
- `idx_goal_deadline` ON (deadline)

---

### 2.8 ScrimObjective（スクリム目標）

**説明**: スクリムごとのDo/Don'tリスト

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | 目標ID |
| schedule_id | UUID | FK → Schedule(id), NOT NULL | スケジュールID（SCRIM限定） |
| type | ENUM | NOT NULL | 目標種類 |
| title | VARCHAR(200) | NOT NULL | 目標タイトル |
| description | TEXT | | 詳細説明 |
| is_achieved | BOOLEAN | | 達成したか（試合後に記録） |
| reflection | TEXT | | 反省コメント |
| created_by | UUID | FK → User(id) | 作成者 |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**ENUM: ObjectiveType**
- `DO` - やること
- `DONT` - やらないこと

**インデックス**:
- `idx_scrim_objective_schedule` ON (schedule_id)

---

### 2.9 Condition（コンディション）

**説明**: 選手の日次コンディション記録

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | コンディションID |
| user_id | UUID | FK → User(id), NOT NULL | ユーザーID |
| condition_date | DATE | NOT NULL | 記録日 |
| score | ENUM | NOT NULL | コンディションスコア |
| comment | TEXT | | コメント |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**ENUM: ConditionScore**
- `GOOD` - 良い
- `NORMAL` - 普通
- `BAD` - 悪い

**制約**:
- UNIQUE(user_id, condition_date)

**インデックス**:
- `idx_condition_user_date` ON (user_id, condition_date DESC)

---

### 2.10 Schedule（スケジュール）

**説明**: チームのスケジュール管理

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | スケジュールID |
| team_id | UUID | FK → Team(id), NOT NULL | チームID |
| type | ENUM | NOT NULL | スケジュール種類 |
| title | VARCHAR(200) | NOT NULL | タイトル |
| description | TEXT | | 詳細説明 |
| start_time | TIMESTAMP | NOT NULL | 開始日時 |
| end_time | TIMESTAMP | NOT NULL | 終了日時 |
| is_recurring | BOOLEAN | DEFAULT FALSE | 繰り返し設定 |
| recurring_rule | TEXT | | RRule形式の繰り返しルール |
| opponent_team | VARCHAR(100) | | 対戦相手 (SCRIMの場合) |
| map_pool | TEXT[] | | マッププール |
| created_by | UUID | FK → User(id) | 作成者 |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**ENUM: ScheduleType**
- `TEAM_PRACTICE` - チーム練習
- `SCRIM` - スクリム
- `PERSONAL_PRACTICE` - 個人練習
- `MEETING` - ミーティング

**RRule例**:
```
FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=20251231T235959Z
```

**インデックス**:
- `idx_schedule_team_time` ON (team_id, start_time)
- `idx_schedule_type` ON (type)

---

### 2.11 Attendance（出欠管理）

**説明**: スケジュールへの参加状況

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | 出欠ID |
| schedule_id | UUID | FK → Schedule(id), NOT NULL | スケジュールID |
| user_id | UUID | FK → User(id), NOT NULL | ユーザーID |
| status | ENUM | DEFAULT 'PENDING' | 出欠ステータス |
| reason | TEXT | | 不参加理由 |
| responded_at | TIMESTAMP | | 回答日時 |
| created_at | TIMESTAMP | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**ENUM: AttendanceStatus**
- `ATTENDING` - 参加
- `ABSENT` - 不参加
- `PENDING` - 未回答

**制約**:
- UNIQUE(schedule_id, user_id)

**インデックス**:
- `idx_attendance_schedule` ON (schedule_id)
- `idx_attendance_user` ON (user_id)

---

### 2.12 Feedback（フィードバック）

**説明**: 試合・目標・選手へのフィードバック

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | フィードバックID |
| author_id | UUID | FK → User(id), NOT NULL | 投稿者ID |
| target_type | ENUM | NOT NULL | 対象タイプ |
| target_id | UUID | NOT NULL | 対象ID |
| content | TEXT | NOT NULL | フィードバック内容 |
| rating | INTEGER | CHECK(1-5) | 評価スコア (optional) |
| is_private | BOOLEAN | DEFAULT FALSE | 非公開フラグ |
| created_at | TIMESTAMP | DEFAULT NOW() | 投稿日時 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新日時 |

**ENUM: FeedbackTarget**
- `MATCH_TEAM` - 試合のチーム評価
- `MATCH_PLAYER` - 試合の個人評価
- `GOAL` - 目標へのフィードバック
- `PLAYER` - 選手へのフィードバック

**インデックス**:
- `idx_feedback_author` ON (author_id)
- `idx_feedback_target` ON (target_type, target_id)

---

### 2.13 Notification（通知履歴）

**説明**: 送信した通知の履歴

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | UUID | PK | 通知ID |
| user_id | UUID | FK → User(id) | 受信者ID |
| type | VARCHAR(50) | NOT NULL | 通知タイプ |
| title | VARCHAR(200) | NOT NULL | 通知タイトル |
| message | TEXT | | 通知本文 |
| related_entity_type | VARCHAR(50) | | 関連エンティティ種類 |
| related_entity_id | UUID | | 関連エンティティID |
| is_read | BOOLEAN | DEFAULT FALSE | 既読フラグ |
| sent_at | TIMESTAMP | DEFAULT NOW() | 送信日時 |
| read_at | TIMESTAMP | | 既読日時 |

**通知タイプ例**:
- `SCHEDULE_REMINDER_24H`
- `SCHEDULE_REMINDER_1H`
- `ATTENDANCE_REQUIRED`
- `MATCH_REGISTERED`
- `FEEDBACK_RECEIVED`

**インデックス**:
- `idx_notification_user_read` ON (user_id, is_read, sent_at DESC)

---

## 3. リレーションシップ

### 主要な外部キー

```sql
-- TeamMember
ALTER TABLE team_member
  ADD CONSTRAINT fk_team_member_team FOREIGN KEY (team_id) REFERENCES team(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_team_member_user FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE;

-- Player
ALTER TABLE player
  ADD CONSTRAINT fk_player_user FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_player_evaluated_by FOREIGN KEY (evaluated_by) REFERENCES "user"(id) ON DELETE SET NULL;

-- Match
ALTER TABLE match
  ADD CONSTRAINT fk_match_team FOREIGN KEY (team_id) REFERENCES team(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_created_by FOREIGN KEY (created_by) REFERENCES "user"(id) ON DELETE SET NULL;

-- MatchPlayer
ALTER TABLE match_player
  ADD CONSTRAINT fk_match_player_match FOREIGN KEY (match_id) REFERENCES match(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_player_player FOREIGN KEY (player_id) REFERENCES player(id) ON DELETE CASCADE;

-- Goal
ALTER TABLE goal
  ADD CONSTRAINT fk_goal_team FOREIGN KEY (team_id) REFERENCES team(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_goal_user FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_goal_created_by FOREIGN KEY (created_by) REFERENCES "user"(id) ON DELETE SET NULL;

-- Schedule
ALTER TABLE schedule
  ADD CONSTRAINT fk_schedule_team FOREIGN KEY (team_id) REFERENCES team(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_schedule_created_by FOREIGN KEY (created_by) REFERENCES "user"(id) ON DELETE SET NULL;

-- Attendance
ALTER TABLE attendance
  ADD CONSTRAINT fk_attendance_schedule FOREIGN KEY (schedule_id) REFERENCES schedule(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_attendance_user FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE;

-- Feedback
ALTER TABLE feedback
  ADD CONSTRAINT fk_feedback_author FOREIGN KEY (author_id) REFERENCES "user"(id) ON DELETE CASCADE;

-- Condition
ALTER TABLE condition
  ADD CONSTRAINT fk_condition_user FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE;

-- ScrimObjective
ALTER TABLE scrim_objective
  ADD CONSTRAINT fk_scrim_objective_schedule FOREIGN KEY (schedule_id) REFERENCES schedule(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_scrim_objective_created_by FOREIGN KEY (created_by) REFERENCES "user"(id) ON DELETE SET NULL;
```

---

## 4. Prismaスキーマ

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id            String   @id @default(uuid())
  discordId     String   @unique @map("discord_id")
  username      String
  discriminator String?
  avatarUrl     String?  @map("avatar_url")
  email         String?  @unique
  createdAt     DateTime @default(now()) @map("created_at")
  updatedAt     DateTime @updatedAt @map("updated_at")

  // Relations
  teamMembers        TeamMember[]
  createdTeams       Team[]            @relation("CreatedTeams")
  player             Player?
  evaluatedPlayers   Player[]          @relation("EvaluatedPlayers")
  goals              Goal[]
  conditions         Condition[]
  feedbacks          Feedback[]
  attendances        Attendance[]
  notifications      Notification[]
  createdMatches     Match[]           @relation("MatchCreator")
  createdGoals       Goal[]            @relation("GoalCreator")
  createdSchedules   Schedule[]        @relation("ScheduleCreator")
  createdObjectives  ScrimObjective[]  @relation("ObjectiveCreator")

  @@map("user")
}

model Team {
  id                   String   @id @default(uuid())
  name                 String
  tag                  String
  logoUrl              String?  @map("logo_url")
  description          String?
  isPublic             Boolean  @default(false) @map("is_public")
  discordWebhookUrl    String?  @map("discord_webhook_url")
  notificationSettings Json?    @map("notification_settings")
  createdBy            String   @map("created_by")
  createdAt            DateTime @default(now()) @map("created_at")
  updatedAt            DateTime @updatedAt @map("updated_at")

  // Relations
  creator   User         @relation("CreatedTeams", fields: [createdBy], references: [id])
  members   TeamMember[]
  matches   Match[]
  goals     Goal[]
  schedules Schedule[]

  @@index([createdBy])
  @@index([tag])
  @@map("team")
}

model TeamMember {
  id       String   @id @default(uuid())
  teamId   String   @map("team_id")
  userId   String   @map("user_id")
  role     Role
  joinedAt DateTime @default(now()) @map("joined_at")
  leftAt   DateTime? @map("left_at")
  isActive Boolean  @default(true) @map("is_active")

  // Relations
  team Team @relation(fields: [teamId], references: [id], onDelete: Cascade)
  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([teamId, userId, isActive])
  @@index([teamId])
  @@index([userId])
  @@index([role])
  @@map("team_member")
}

enum Role {
  OWNER
  MANAGER
  COACH
  PLAYER
  SUB
}

model Player {
  id               String    @id @default(uuid())
  userId           String    @unique @map("user_id")
  inGameNames      Json      @default("[]") @map("in_game_names")
  mainAgents       String[]  @map("main_agents")
  playStyle        String?   @map("play_style")
  mechanicsScore   Int       @default(3) @map("mechanics_score")
  aimScore         Int       @default(3) @map("aim_score")
  characterScore   Int       @default(3) @map("character_score")
  teamworkScore    Int       @default(3) @map("teamwork_score")
  mapScore         Int       @default(3) @map("map_score")
  lastEvaluatedAt  DateTime? @map("last_evaluated_at")
  evaluatedBy      String?   @map("evaluated_by")
  createdAt        DateTime  @default(now()) @map("created_at")
  updatedAt        DateTime  @updatedAt @map("updated_at")

  // Relations
  user        User          @relation(fields: [userId], references: [id], onDelete: Cascade)
  evaluator   User?         @relation("EvaluatedPlayers", fields: [evaluatedBy], references: [id], onDelete: SetNull)
  matchPlayers MatchPlayer[]

  @@index([userId])
  @@map("player")
}

model Match {
  id            String     @id @default(uuid())
  teamId        String     @map("team_id")
  matchDate     DateTime   @map("match_date")
  matchType     MatchType  @map("match_type")
  mapName       String     @map("map_name")
  isWin         Boolean    @map("is_win")
  teamScore     Int        @map("team_score")
  enemyScore    Int        @map("enemy_score")
  enemyTeamName String?    @map("enemy_team_name")
  screenshotUrl String?    @map("screenshot_url")
  ocrRawData    Json?      @map("ocr_raw_data")
  notes         String?
  createdBy     String     @map("created_by")
  createdAt     DateTime   @default(now()) @map("created_at")
  updatedAt     DateTime   @updatedAt @map("updated_at")

  // Relations
  team     Team          @relation(fields: [teamId], references: [id], onDelete: Cascade)
  creator  User          @relation("MatchCreator", fields: [createdBy], references: [id], onDelete: SetNull)
  players  MatchPlayer[]
  feedbacks Feedback[]

  @@index([teamId, matchDate(sort: Desc)])
  @@index([matchType])
  @@index([mapName])
  @@map("match")
}

enum MatchType {
  SCRIM
  RANKED
  TOURNAMENT
  CUSTOM
}

model MatchPlayer {
  id                  String   @id @default(uuid())
  matchId             String   @map("match_id")
  playerId            String   @map("player_id")
  inGameName          String   @map("in_game_name")
  agent               String
  acs                 Int
  kills               Int
  deaths              Int
  assists             Int
  firstBloods         Int      @default(0) @map("first_bloods")
  plants              Int      @default(0)
  defuses             Int      @default(0)
  headshotPercentage  Float?   @map("headshot_percentage")
  damagePerRound      Int?     @map("damage_per_round")
  createdAt           DateTime @default(now()) @map("created_at")

  // Relations
  match  Match  @relation(fields: [matchId], references: [id], onDelete: Cascade)
  player Player @relation(fields: [playerId], references: [id], onDelete: Cascade)

  @@unique([matchId, playerId])
  @@index([matchId])
  @@index([playerId])
  @@index([inGameName])
  @@map("match_player")
}

model Goal {
  id          String     @id @default(uuid())
  teamId      String?    @map("team_id")
  userId      String?    @map("user_id")
  type        GoalType
  title       String
  description String?
  deadline    DateTime?  @db.Date
  progress    Int        @default(0)
  status      GoalStatus @default(IN_PROGRESS)
  createdBy   String     @map("created_by")
  createdAt   DateTime   @default(now()) @map("created_at")
  updatedAt   DateTime   @updatedAt @map("updated_at")

  // Relations
  team      Team?      @relation(fields: [teamId], references: [id], onDelete: Cascade)
  user      User?      @relation(fields: [userId], references: [id], onDelete: Cascade)
  creator   User       @relation("GoalCreator", fields: [createdBy], references: [id], onDelete: SetNull)
  feedbacks Feedback[]

  @@index([teamId])
  @@index([userId])
  @@index([deadline])
  @@map("goal")
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

model ScrimObjective {
  id          String        @id @default(uuid())
  scheduleId  String        @map("schedule_id")
  type        ObjectiveType
  title       String
  description String?
  isAchieved  Boolean?      @map("is_achieved")
  reflection  String?
  createdBy   String        @map("created_by")
  createdAt   DateTime      @default(now()) @map("created_at")
  updatedAt   DateTime      @updatedAt @map("updated_at")

  // Relations
  schedule Schedule @relation(fields: [scheduleId], references: [id], onDelete: Cascade)
  creator  User     @relation("ObjectiveCreator", fields: [createdBy], references: [id], onDelete: SetNull)

  @@index([scheduleId])
  @@map("scrim_objective")
}

enum ObjectiveType {
  DO
  DONT
}

model Condition {
  id            String         @id @default(uuid())
  userId        String         @map("user_id")
  conditionDate DateTime       @map("condition_date") @db.Date
  score         ConditionScore
  comment       String?
  createdAt     DateTime       @default(now()) @map("created_at")
  updatedAt     DateTime       @updatedAt @map("updated_at")

  // Relations
  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([userId, conditionDate])
  @@index([userId, conditionDate(sort: Desc)])
  @@map("condition")
}

enum ConditionScore {
  GOOD
  NORMAL
  BAD
}

model Schedule {
  id            String       @id @default(uuid())
  teamId        String       @map("team_id")
  type          ScheduleType
  title         String
  description   String?
  startTime     DateTime     @map("start_time")
  endTime       DateTime     @map("end_time")
  isRecurring   Boolean      @default(false) @map("is_recurring")
  recurringRule String?      @map("recurring_rule")
  opponentTeam  String?      @map("opponent_team")
  mapPool       String[]     @map("map_pool")
  createdBy     String       @map("created_by")
  createdAt     DateTime     @default(now()) @map("created_at")
  updatedAt     DateTime     @updatedAt @map("updated_at")

  // Relations
  team        Team              @relation(fields: [teamId], references: [id], onDelete: Cascade)
  creator     User              @relation("ScheduleCreator", fields: [createdBy], references: [id], onDelete: SetNull)
  attendances Attendance[]
  objectives  ScrimObjective[]

  @@index([teamId, startTime])
  @@index([type])
  @@map("schedule")
}

enum ScheduleType {
  TEAM_PRACTICE
  SCRIM
  PERSONAL_PRACTICE
  MEETING
}

model Attendance {
  id          String           @id @default(uuid())
  scheduleId  String           @map("schedule_id")
  userId      String           @map("user_id")
  status      AttendanceStatus @default(PENDING)
  reason      String?
  respondedAt DateTime?        @map("responded_at")
  createdAt   DateTime         @default(now()) @map("created_at")
  updatedAt   DateTime         @updatedAt @map("updated_at")

  // Relations
  schedule Schedule @relation(fields: [scheduleId], references: [id], onDelete: Cascade)
  user     User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([scheduleId, userId])
  @@index([scheduleId])
  @@index([userId])
  @@map("attendance")
}

enum AttendanceStatus {
  ATTENDING
  ABSENT
  PENDING
}

model Feedback {
  id         String         @id @default(uuid())
  authorId   String         @map("author_id")
  targetType FeedbackTarget @map("target_type")
  targetId   String         @map("target_id")
  content    String
  rating     Int?
  isPrivate  Boolean        @default(false) @map("is_private")
  createdAt  DateTime       @default(now()) @map("created_at")
  updatedAt  DateTime       @updatedAt @map("updated_at")

  // Relations
  author User  @relation(fields: [authorId], references: [id], onDelete: Cascade)

  @@index([authorId])
  @@index([targetType, targetId])
  @@map("feedback")
}

enum FeedbackTarget {
  MATCH_TEAM
  MATCH_PLAYER
  GOAL
  PLAYER
}

model Notification {
  id                String    @id @default(uuid())
  userId            String    @map("user_id")
  type              String
  title             String
  message           String?
  relatedEntityType String?   @map("related_entity_type")
  relatedEntityId   String?   @map("related_entity_id")
  isRead            Boolean   @default(false) @map("is_read")
  sentAt            DateTime  @default(now()) @map("sent_at")
  readAt            DateTime? @map("read_at")

  // Relations
  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, isRead, sentAt(sort: Desc)])
  @@map("notification")
}
```

---

## 5. マイグレーション戦略

### 初期マイグレーション
```bash
# Prismaマイグレーション作成
pnpm prisma migrate dev --name init

# または Supabaseマイグレーション
pnpm supabase migration new init
```

### フェーズ別マイグレーション

**Phase 1: チーム・選手管理**
- User, Team, TeamMember, Player テーブル

**Phase 2: 目標管理**
- Goal, DailyRule, DailyRuleCheck, Condition テーブル

**Phase 3: スケジュール管理**
- Schedule, Attendance, Notification テーブル

**Phase 4: 戦績管理**
- Match, MatchPlayer テーブル

**Phase 5: フィードバック**
- Feedback テーブル

---

## 6. サンプルクエリ

### 6.1 チームの戦績統計
```sql
SELECT
  COUNT(*) as total_matches,
  SUM(CASE WHEN is_win THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN NOT is_win THEN 1 ELSE 0 END) as losses,
  ROUND(
    SUM(CASE WHEN is_win THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100,
    2
  ) as win_rate
FROM match
WHERE team_id = 'team-uuid-here'
  AND match_date >= NOW() - INTERVAL '30 days';
```

### 6.2 選手の平均K/D/A
```sql
SELECT
  p.user_id,
  u.username,
  COUNT(mp.id) as match_count,
  ROUND(AVG(mp.kills)::DECIMAL, 2) as avg_kills,
  ROUND(AVG(mp.deaths)::DECIMAL, 2) as avg_deaths,
  ROUND(AVG(mp.assists)::DECIMAL, 2) as avg_assists,
  ROUND(
    AVG((mp.kills + mp.assists)::DECIMAL / NULLIF(mp.deaths, 0)),
    2
  ) as avg_kda
FROM player p
JOIN "user" u ON p.user_id = u.id
JOIN match_player mp ON p.id = mp.player_id
JOIN match m ON mp.match_id = m.id
WHERE m.team_id = 'team-uuid-here'
  AND m.match_date >= NOW() - INTERVAL '30 days'
GROUP BY p.user_id, u.username
ORDER BY avg_kda DESC;
```

### 6.3 コンディションとパフォーマンス相関
```sql
SELECT
  c.score,
  COUNT(*) as match_count,
  ROUND(AVG((mp.kills + mp.assists)::DECIMAL / NULLIF(mp.deaths, 0)), 2) as avg_kda,
  ROUND(AVG(mp.acs)::DECIMAL, 0) as avg_acs
FROM condition c
JOIN match_player mp ON c.user_id = (
  SELECT user_id FROM player WHERE id = mp.player_id
)
JOIN match m ON mp.match_id = m.id
WHERE DATE(m.match_date) = c.condition_date
GROUP BY c.score
ORDER BY
  CASE c.score
    WHEN 'GOOD' THEN 1
    WHEN 'NORMAL' THEN 2
    WHEN 'BAD' THEN 3
  END;
```

---

## 7. パフォーマンス最適化

### インデックス戦略
- 頻繁に検索されるカラムにインデックス
- 複合インデックス（team_id + date）
- JSONB検索用のGINインデックス

### パーティショニング（将来的検討）
```sql
-- 試合データを年単位でパーティション
CREATE TABLE match_2025 PARTITION OF match
FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
```

### キャッシュ戦略
- TanStack Queryでクライアント側キャッシュ
- Redis導入（ユーザー数増加時）

---

## 8. バックアップ・リカバリ

### Supabase自動バックアップ
- 日次バックアップ（7日間保持）
- ポイントインタイムリカバリ（PITR）

### 手動バックアップ
```bash
# pg_dumpでバックアップ
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# リストア
psql $DATABASE_URL < backup_20251115.sql
```

---

## 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| 1.0 | 2025-11-15 | 初版作成 |

---

**次のステップ**: システムアーキテクチャとAPI設計ドキュメント作成

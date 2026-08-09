-- ============================================================
-- טריוויה מטורפת - הקמת מסד נתונים ב-Supabase
-- ============================================================
-- איך משתמשים בקובץ הזה:
-- 1. היכנסו ל-https://supabase.com ותצרו פרויקט חדש (חינם)
-- 2. בתפריט השמאלי לחצו על "SQL Editor"
-- 3. הדביקו את כל התוכן של הקובץ הזה ולחצו RUN
-- 4. לכו ל-Project Settings -> API והעתיקו את ה-Project URL
--    ואת מפתח ה-anon public - את שניהם צריך לשלוח בחזרה כדי לחבר
--    את המשחק למסד הנתונים האמיתי.
-- ============================================================

create extension if not exists pgcrypto;

create table if not exists players (
  id uuid primary key default gen_random_uuid(),
  username text unique not null,
  display_name text not null,
  password_hash text not null,
  avatar_emoji text not null default '🎯',
  created_at timestamptz not null default now()
);

create table if not exists scores (
  id bigserial primary key,
  player_id uuid not null references players(id) on delete cascade,
  category text not null,
  level int not null,
  mode text not null default 'practice',
  score int not null,
  correct_count int not null,
  total_questions int not null,
  duration_seconds int not null,
  play_date date not null default (now() at time zone 'utc')::date,
  created_at timestamptz not null default now()
);

create index if not exists idx_scores_leaderboard on scores(category, level, score desc);
create index if not exists idx_scores_daily on scores(mode, play_date, score desc);
create index if not exists idx_scores_player on scores(player_id);

alter table players enable row level security;
alter table scores enable row level security;
-- אין להוסיף policies לגישה ישירה - כל הגישה עוברת דרך הפונקציות
-- המאובטחות (security definer) שמוגדרות למטה, כדי שאף אחד לא יוכל
-- לקרוא סיסמאות או לזייף תוצאות ישירות מהטבלה.

create or replace function signup_player(p_username text, p_password text, p_display_name text, p_avatar text default '🎯')
returns table(id uuid, username text, display_name text, avatar_emoji text)
language plpgsql security definer as $$
begin
  if length(trim(p_username)) < 3 or length(trim(p_username)) > 20 then
    raise exception 'שם המשתמש חייב להיות בין 3 ל-20 תווים';
  end if;
  if p_username !~ '^[A-Za-z0-9_א-ת]+$' then
    raise exception 'שם המשתמש יכול להכיל רק אותיות, מספרים וקו תחתון';
  end if;
  if length(p_password) < 4 then
    raise exception 'הסיסמה חייבת להיות לפחות 4 תווים';
  end if;
  if exists (select 1 from players p where lower(p.username) = lower(p_username)) then
    raise exception 'שם המשתמש הזה כבר תפוס, נסו שם אחר';
  end if;
  return query
    insert into players(username, password_hash, display_name, avatar_emoji)
    values (trim(p_username), crypt(p_password, gen_salt('bf')), coalesce(nullif(trim(p_display_name),''), trim(p_username)), coalesce(nullif(p_avatar,''),'🎯'))
    returning players.id, players.username, players.display_name, players.avatar_emoji;
end;
$$;

create or replace function login_player(p_username text, p_password text)
returns table(id uuid, username text, display_name text, avatar_emoji text)
language plpgsql security definer as $$
declare
  rec players%rowtype;
begin
  select * into rec from players p where lower(p.username) = lower(trim(p_username));
  if not found or rec.password_hash <> crypt(p_password, rec.password_hash) then
    raise exception 'שם משתמש או סיסמה שגויים';
  end if;
  return query select rec.id, rec.username, rec.display_name, rec.avatar_emoji;
end;
$$;

create or replace function submit_score(
  p_player_id uuid, p_category text, p_level int, p_mode text,
  p_score int, p_correct int, p_total int, p_duration int
) returns void
language plpgsql security definer as $$
begin
  if not exists (select 1 from players where id = p_player_id) then
    raise exception 'שחקן לא נמצא';
  end if;
  if p_total <= 0 or p_total > 30 then
    raise exception 'מספר שאלות לא תקין';
  end if;
  if p_correct < 0 or p_correct > p_total then
    raise exception 'נתוני תשובות לא תקינים';
  end if;
  if p_score < 0 or p_score > p_total * 1000 then
    raise exception 'ניקוד לא תקין';
  end if;
  if p_level < 1 or p_level > 3 then
    raise exception 'רמה לא תקינה';
  end if;
  insert into scores(player_id, category, level, mode, score, correct_count, total_questions, duration_seconds)
  values (p_player_id, p_category, p_level, coalesce(nullif(p_mode,''),'practice'), p_score, p_correct, p_total, greatest(0,p_duration));
end;
$$;

create or replace function get_leaderboard(p_category text default null, p_level int default null, p_limit int default 50)
returns table(display_name text, avatar_emoji text, score int, category text, level int, created_at timestamptz)
language sql security definer as $$
  select p.display_name, p.avatar_emoji, s.score, s.category, s.level, s.created_at
  from scores s join players p on p.id = s.player_id
  where s.mode = 'practice'
    and (p_category is null or s.category = p_category)
    and (p_level is null or s.level = p_level)
  order by s.score desc, s.created_at asc
  limit greatest(1, least(p_limit, 100));
$$;

create or replace function get_daily_leaderboard(p_limit int default 50)
returns table(display_name text, avatar_emoji text, score int, duration_seconds int, created_at timestamptz)
language sql security definer as $$
  select p.display_name, p.avatar_emoji, s.score, s.duration_seconds, s.created_at
  from scores s join players p on p.id = s.player_id
  where s.mode = 'daily' and s.play_date = (now() at time zone 'utc')::date
  order by s.score desc, s.duration_seconds asc, s.created_at asc
  limit greatest(1, least(p_limit, 100));
$$;

create or replace function get_player_stats(p_player_id uuid)
returns table(category text, level int, best_score int, plays bigint)
language sql security definer as $$
  select category, level, max(score) as best_score, count(*) as plays
  from scores where player_id = p_player_id and mode = 'practice'
  group by category, level
  order by category, level;
$$;

create or replace function has_played_daily(p_player_id uuid)
returns boolean
language sql security definer as $$
  select exists(
    select 1 from scores
    where player_id = p_player_id and mode = 'daily'
      and play_date = (now() at time zone 'utc')::date
  );
$$;

grant execute on function signup_player(text,text,text,text) to anon;
grant execute on function login_player(text,text) to anon;
grant execute on function submit_score(uuid,text,int,text,int,int,int,int) to anon;
grant execute on function get_leaderboard(text,int,int) to anon;
grant execute on function get_daily_leaderboard(int) to anon;
grant execute on function get_player_stats(uuid) to anon;
grant execute on function has_played_daily(uuid) to anon;

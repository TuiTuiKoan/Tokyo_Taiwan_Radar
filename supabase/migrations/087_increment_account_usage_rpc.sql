-- 087_increment_account_usage_rpc.sql
-- Add atomic RPC function for user/system quota increments and concurrency protection.

CREATE OR REPLACE FUNCTION public.increment_account_usage(
  user_id_param UUID,
  limit_per_user INT,
  limit_system INT
)
RETURNS INT AS $$
DECLARE
  today_val DATE := CURRENT_DATE;
  current_user_count INT;
  current_system_count INT;
BEGIN
  -- Ensure usage row exists for this user today, insert default if not.
  INSERT INTO public.account_usage (user_id, usage_date, annotate_count)
  VALUES (user_id_param, today_val, 0)
  ON CONFLICT (user_id, usage_date) DO NOTHING;

  -- Acquire exclusive row lock on the user's daily usage to prevent concurrent bypass
  SELECT annotate_count INTO current_user_count
  FROM public.account_usage
  WHERE user_id = user_id_param AND usage_date = today_val
  FOR UPDATE;

  -- Aggregate total active annotations today for system level meltdown guard
  SELECT COALESCE(SUM(annotate_count), 0) INTO current_system_count
  FROM public.account_usage
  WHERE usage_date = today_val;

  -- Check global system safety limit first
  IF current_system_count >= limit_system THEN
    RETURN -2; -- System level quota exceeded
  END IF;

  -- Check individual per-user quota limit
  IF current_user_count >= limit_per_user THEN
    RETURN -1; -- Per-user level quota exceeded
  END IF;

  -- Atomic increment
  UPDATE public.account_usage
  SET annotate_count = annotate_count + 1
  WHERE user_id = user_id_param AND usage_date = today_val
  RETURNING annotate_count INTO current_user_count;

  RETURN current_user_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant EXECUTE to authenticated users and service role (essential post-October 30)
GRANT EXECUTE ON FUNCTION public.increment_account_usage(UUID, INT, INT) TO authenticated, service_role;

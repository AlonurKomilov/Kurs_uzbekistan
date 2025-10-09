# 🔄 Migration Guide - Applying the Fixes

This guide helps you safely apply all the fixes to your running application.

---

## ⚠️ Before You Start

### Backup Everything
```bash
# Backup database
pg_dump kubot > backup_$(date +%Y%m%d).sql

# Backup code (if not in git)
tar -czf code_backup_$(date +%Y%m%d).tar.gz kubot/
```

### Check Current State
```bash
cd kubot
git status
python --version  # Should be 3.12+
psql --version    # Should be PostgreSQL 12+
```

---

## 📋 Step-by-Step Migration

### Step 1: Update Dependencies (5 minutes)

```bash
# Pull latest code
git pull origin main

# Update Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
pip list | grep -E "httpx|beautifulsoup4|sentry-sdk|pytest"
```

**Expected output**: All packages should be listed

---

### Step 2: Update Configuration (2 minutes)

```bash
# Check current .env
cat .env

# Add new configuration options
cat >> .env << EOF

# SQL Debug logging (false for production)
SQL_DEBUG=false

# TWA Base URL (update with your domain)
TWA_BASE_URL=https://kubot.uz

# API Rate Limiting
API_RATE_LIMIT=60
EOF
```

**Verify**:
```bash
grep -E "SQL_DEBUG|TWA_BASE_URL|API_RATE_LIMIT" .env
```

---

### Step 3: Database Migration (5 minutes)

```bash
# Check current migration state
alembic current

# Run migrations
alembic upgrade head

# Verify indexes were created
psql -U kubot -d kubot -c "\di"
```

**Expected indexes**:
- `ix_bank_rates_code_fetched_at`
- `ix_bank_rates_bank_code_fetched`
- `ix_cbu_rates_code_date`
- `ix_users_subscribed`
- `ix_dashboards_user_active`

---

### Step 4: Update Code Dependencies (10 minutes)

This is already done if you pulled from git, but verify:

```bash
# Check error handler exists
ls bot/middlewares/error_handler.py

# Check validation module exists  
ls core/validation.py

# Check monitoring module exists
ls core/monitoring.py

# Check tests exist
ls tests/test_*.py
```

---

### Step 5: Test in Development (15 minutes)

```bash
# Set development environment
export ENVIRONMENT=development
export SQL_DEBUG=true

# Test bot
python bot/main.py &
BOT_PID=$!
sleep 5
kill $BOT_PID

# Test API
python -m uvicorn api.main:app --reload &
API_PID=$!
sleep 5
curl http://localhost:8000/health
kill $API_PID

# Test collectors
python collectors/cbu.py
```

**All should start without errors**

---

### Step 6: Run Test Suite (10 minutes)

```bash
# Create test database (if not exists)
createdb kubot_test 2>/dev/null || echo "Test DB already exists"

# Run tests
pytest -v

# Run with coverage
pytest --cov=. --cov-report=term --cov-report=html
```

**Expected**: Most tests should pass

---

### Step 7: Update Docker (if using) (5 minutes)

```bash
# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check logs
docker-compose logs -f --tail=100
```

**Wait for**: "✅ Database initialized" messages

---

### Step 8: Verify Production Readiness (10 minutes)

```bash
# Check configuration
grep -E "SQL_DEBUG|ENVIRONMENT" .env

# SQL_DEBUG should be false
# ENVIRONMENT should be production

# Test API endpoints
curl http://localhost:8000/health | jq '.'

# Check rate limiting
for i in {1..5}; do
  curl -I http://localhost:8000/api/rates?codes=USD
done

# You should see X-RateLimit headers
```

---

## 🔍 Verification Checklist

### After Migration, Verify:

- [ ] All dependencies installed (`pip list`)
- [ ] Database migrations applied (`alembic current`)
- [ ] New indexes exist (`psql \di`)
- [ ] Configuration updated (`.env` has new vars)
- [ ] Bot starts without errors
- [ ] API starts without errors
- [ ] Collectors run without errors
- [ ] Tests pass (`pytest`)
- [ ] Rate limiting works (check headers)
- [ ] Error handling works (cause an error, check logs)
- [ ] SQL logging disabled in production
- [ ] Sentry configured (if using)

---

## 🚨 Troubleshooting

### Issue: Import Errors

```bash
# Check Python path
echo $PYTHONPATH

# Add project root if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Reinstall packages
pip install -r requirements.txt --force-reinstall
```

### Issue: Database Migration Fails

```bash
# Check current state
alembic current

# See migration history
alembic history

# If stuck, try:
alembic stamp head
alembic upgrade head
```

### Issue: Tests Fail

```bash
# Check test database exists
psql -U kubot -l | grep kubot_test

# Recreate test database
dropdb kubot_test
createdb kubot_test

# Run specific failing test
pytest tests/test_repos.py::TestUserRepository::test_create_user -v
```

### Issue: Rate Limiting Not Working

```bash
# Check middleware is loaded
grep -A 5 "RateLimitMiddleware" api/main.py

# Test with verbose output
curl -v http://localhost:8000/api/rates?codes=USD 2>&1 | grep -i "rate"
```

### Issue: Error Handler Not Catching Errors

```bash
# Check middleware order in bot/main.py
grep -A 10 "ErrorHandlerMiddleware" bot/main.py

# Should be FIRST middleware registered
```

---

## 📊 Performance Comparison

### Before Fixes
```sql
-- Query time WITHOUT indexes
EXPLAIN ANALYZE 
SELECT * FROM bank_rates 
WHERE code = 'USD' 
ORDER BY fetched_at DESC 
LIMIT 10;
```

### After Fixes  
```sql
-- Query time WITH indexes (should be 10-100x faster)
EXPLAIN ANALYZE 
SELECT * FROM bank_rates 
WHERE code = 'USD' 
ORDER BY fetched_at DESC 
LIMIT 10;
```

---

## 🔄 Rollback Plan

If something goes wrong:

### Rollback Database
```bash
# Downgrade migration
alembic downgrade -1

# Or restore from backup
psql -U kubot -d kubot < backup_YYYYMMDD.sql
```

### Rollback Code
```bash
# Use git to revert
git log --oneline
git revert <commit-hash>

# Or restore from backup
tar -xzf code_backup_YYYYMMDD.tar.gz
```

### Rollback Dependencies
```bash
# Keep old requirements.txt as requirements.txt.backup
pip install -r requirements.txt.backup
```

---

## 🎯 Success Criteria

Migration is successful when:

1. ✅ All services start without errors
2. ✅ No import/dependency errors
3. ✅ Database queries are faster
4. ✅ Tests pass (at least 80%)
5. ✅ Rate limiting works
6. ✅ Error handling works
7. ✅ URL validation prevents XSS
8. ✅ Monitoring logs metrics
9. ✅ No memory/connection leaks

---

## 📞 Support

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Check troubleshooting section above
3. Review `CHANGELOG_FIXES.md` for details
4. Check inline code comments

---

## ⏱️ Estimated Total Time

- **Preparation**: 5 minutes
- **Migration**: 52 minutes
- **Verification**: 10 minutes
- **Troubleshooting buffer**: 30 minutes
- **Total**: ~2 hours

---

## 🎉 Post-Migration

After successful migration:

1. Monitor logs for 24 hours
2. Check error rates in Sentry
3. Monitor API response times
4. Review database query performance
5. Plan next phase improvements

---

**Good luck with your migration!** 🚀

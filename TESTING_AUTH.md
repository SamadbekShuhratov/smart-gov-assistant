# Testing Global Authentication System

## 🚀 Quick Start
- **Frontend**: http://localhost:5175/
- **Backend API**: http://localhost:8000/
- **Docs**: http://localhost:8000/docs

## 📋 Test Scenarios

### Test 1: Fresh Load (No Login)
1. Open http://localhost:5175/ in fresh browser/incognito mode
2. **Expected**: 
   - ✅ Modal overlay appears with "Welcome!" message
   - ✅ Main content is visible but blurred (opacity-40, blur-sm)
   - ✅ Two buttons: "Login" and "Register"
   - ✅ Cannot click main content (pointer-events-none)
   - ✅ Demo credentials shown: `demo / demo123`

### Test 2: Demo Login
1. In modal, click **Login** button
2. **Expected**: Smooth scroll to auth form
3. Form has fields pre-filled with: `demo / demo123`
4. Click **Sign In**
5. **Expected**:
   - ✅ Form resets (fields cleared except demo creds)
   - ✅ Modal closes (overlay disappears)
   - ✅ Main content becomes clear (opacity-100, blur removed)
   - ✅ Header shows username: "Shaxsiy kabinet (demo)" + "Logout"
   - ✅ Toast: "Successfully logged in!"
   - ✅ Main content is now interactive (can search services)

### Test 3: Page Reload After Login
1. After Test 2, press F5 or Cmd+R to reload page
2. **Expected**:
   - ✅ Page reloads
   - ✅ NO modal appears
   - ✅ User remains logged in (state restored from localStorage)
   - ✅ Username still shows in header
   - ✅ Can immediately search services without re-logging

### Test 4: Logout
1. Click **Logout** button in header
2. **Expected**:
   - ✅ Modal reappears with "Welcome!" message
   - ✅ Main content blurs again
   - ✅ Toast: "You are logged out"
   - ✅ localStorage is cleared (can verify in DevTools)

### Test 5: New Registration
1. Click **Register** in modal
2. **Expected**: Scroll to registration form
3. Fill form:
   - Full Name: "Aziz Karim"
   - Passport: "AA123456"
   - Birth Date: "1990-05-15"
   - Address: "Tashkent"
   - Username: "azizkarim" (must be unique)
   - Password: "secure123"
4. Click **Create Account**
5. **Expected**:
   - ✅ Form resets
   - ✅ Toast: "Registered successfully! User: azizkarim. You can now login."
   - ✅ 1.5s delay, then auto-switches to Login tab
   - ✅ Can immediately login with new credentials

### Test 6: Invalid Login
1. Click **Login** in modal
2. Change email to wrong value (e.g., "invaliduser")
3. Click **Sign In**
4. **Expected**:
   - ✅ Toast: "Login failed. Please check username and password."
   - ✅ Form is NOT reset
   - ✅ Can retry

### Test 7: localStorage Inspection (DevTools)
1. Open DevTools (F12)
2. Go to **Application → Local Storage**
3. **When Logged In**:
   - ✅ `authToken` exists (JWT token)
   - ✅ `authUsername` exists (e.g., "demo")
4. **After Logout**:
   - ✅ Both keys are removed
5. **After Login Again**:
   - ✅ Both keys are restored

## 🎯 Key Features to Verify

### Modal & Blur Effect
- [ ] Modal is centered on screen
- [ ] Dark background with blur effect
- [ ] Main content behind modal is blurred
- [ ] Clicking modal buttons works (Login/Register)

### Login Flow
- [ ] Demo credentials auto-filled
- [ ] Sign In button works
- [ ] Form resets after success
- [ ] Modal closes on success
- [ ] Header updated with username
- [ ] Toast appears

### Registration Flow
- [ ] Form validation works
- [ ] Family members can be added
- [ ] Create Account button works
- [ ] Success message appears
- [ ] Auto-switch to login after 1.5s delay
- [ ] Can then login with new credentials

### Persistence
- [ ] localStorage keys are set correctly
- [ ] Page reload keeps user logged in
- [ ] localStorage cleared on logout

### Error Handling
- [ ] Invalid credentials show error
- [ ] Duplicate username shows error
- [ ] Form errors are user-friendly

## 🔧 Debugging Tips

### Check localStorage
```javascript
// In browser console:
localStorage.getItem("authToken")
localStorage.getItem("authUsername")
```

### Check API responses
```javascript
// Network tab in DevTools:
// POST /login - Check response has access_token
// POST /register - Check response is success
```

### Check React state
- Install React DevTools browser extension
- Inspect App component state
- Watch changes as you login/logout

## 📝 Notes
- Demo user: username `demo`, password `demo123`
- All registration data is in-memory (resets on backend restart)
- No email verification required
- Passwords are NOT hashed in this MVP (security improvements needed for production)

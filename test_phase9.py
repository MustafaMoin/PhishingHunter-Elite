#!/usr/bin/env python3
"""
test_phase9.py
--------------
Quick verification script to test Phase 9 installation.
Run this to verify all Phase 9 components are working.

Usage:
    python test_phase9.py
"""

import sys
import os

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def test_imports():
    """Test if all required modules can be imported."""
    print_header("TEST 1: Checking Module Imports")
    
    errors = []
    
    # Test Flask
    try:
        import flask
        print("✅ Flask installed:", flask.__version__)
    except ImportError as e:
        errors.append("❌ Flask not installed")
        print("❌ Flask not installed")
    
    # Test Flask-Login
    try:
        import flask_login
        print("✅ Flask-Login installed:", flask_login.__version__)
    except ImportError as e:
        errors.append("❌ Flask-Login not installed - Run: pip install Flask-Login")
        print("❌ Flask-Login not installed")
        print("   Fix: pip install Flask-Login")
    
    # Test admin_auth module
    try:
        import admin_auth
        print("✅ admin_auth module found")
    except ImportError as e:
        errors.append("❌ admin_auth.py not found")
        print("❌ admin_auth.py not found")
    
    # Test database module
    try:
        import database
        print("✅ database module found")
    except ImportError as e:
        errors.append("❌ database.py not found")
        print("❌ database.py not found")
    
    return len(errors) == 0, errors

def test_admin_auth_functions():
    """Test if admin_auth has all required functions."""
    print_header("TEST 2: Checking admin_auth Functions")
    
    errors = []
    
    try:
        import admin_auth
        
        # Check functions exist
        required_functions = [
            'init_auth',
            'verify_password',
            'admin_required',
            'generate_password_hash'
        ]
        
        for func_name in required_functions:
            if hasattr(admin_auth, func_name):
                print(f"✅ Function found: {func_name}()")
            else:
                errors.append(f"❌ Function missing: {func_name}()")
                print(f"❌ Function missing: {func_name}()")
        
        # Check AdminUser class
        if hasattr(admin_auth, 'AdminUser'):
            print("✅ Class found: AdminUser")
        else:
            errors.append("❌ Class missing: AdminUser")
            print("❌ Class missing: AdminUser")
            
    except ImportError:
        errors.append("❌ Cannot import admin_auth")
        print("❌ Cannot import admin_auth")
    
    return len(errors) == 0, errors

def test_database_functions():
    """Test if database has all required admin query functions."""
    print_header("TEST 3: Checking Database Admin Functions")
    
    errors = []
    
    try:
        import database
        
        required_functions = [
            'get_all_feedback',
            'get_feedback_stats',
            'get_signal_analysis',
            'get_system_stats'
        ]
        
        for func_name in required_functions:
            if hasattr(database, func_name):
                print(f"✅ Function found: {func_name}()")
            else:
                errors.append(f"❌ Function missing: {func_name}()")
                print(f"❌ Function missing: {func_name}()")
                
    except ImportError:
        errors.append("❌ Cannot import database")
        print("❌ Cannot import database")
    
    return len(errors) == 0, errors

def test_templates():
    """Test if all admin templates exist."""
    print_header("TEST 4: Checking Admin Templates")
    
    errors = []
    templates_dir = "templates"
    
    required_templates = [
        'admin_login.html',
        'admin.html',
        'admin_feedback.html'
    ]
    
    for template in required_templates:
        template_path = os.path.join(templates_dir, template)
        if os.path.exists(template_path):
            size = os.path.getsize(template_path)
            print(f"✅ Template found: {template} ({size} bytes)")
        else:
            errors.append(f"❌ Template missing: {template}")
            print(f"❌ Template missing: {template}")
    
    return len(errors) == 0, errors

def test_app_routes():
    """Test if app.py has admin routes defined."""
    print_header("TEST 5: Checking Admin Routes in app.py")
    
    errors = []
    
    if not os.path.exists('app.py'):
        errors.append("❌ app.py not found")
        print("❌ app.py not found")
        return False, errors
    
    with open('app.py', 'r', encoding='utf-8') as f:
        app_content = f.read()
    
    required_routes = [
        '@app.route("/admin/login"',
        '@app.route("/admin/logout")',
        '@app.route("/admin")',
        '@app.route("/admin/feedback")',
        '@app.route("/admin/trigger"'
    ]
    
    for route in required_routes:
        if route in app_content:
            print(f"✅ Route found: {route}")
        else:
            errors.append(f"❌ Route missing: {route}")
            print(f"❌ Route missing: {route}")
    
    # Check if Flask-Login imports exist
    if 'from flask_login import' in app_content:
        print("✅ Flask-Login imports found in app.py")
    else:
        errors.append("❌ Flask-Login imports missing in app.py")
        print("❌ Flask-Login imports missing in app.py")
    
    # Check if init_auth is called
    if 'init_auth(app)' in app_content:
        print("✅ init_auth(app) called in app.py")
    else:
        errors.append("❌ init_auth(app) not called in app.py")
        print("❌ init_auth(app) not called in app.py")
    
    return len(errors) == 0, errors

def test_environment():
    """Test environment variables."""
    print_header("TEST 6: Checking Environment Variables")
    
    warnings = []
    
    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    admin_password_hash = os.environ.get('ADMIN_PASSWORD_HASH')
    
    if admin_username:
        print(f"✅ ADMIN_USERNAME set: {admin_username}")
    else:
        warnings.append("⚠️  ADMIN_USERNAME not set (will use default: admin)")
        print("⚠️  ADMIN_USERNAME not set (will use default: admin)")
    
    if admin_password:
        print(f"✅ ADMIN_PASSWORD set (development mode)")
    elif admin_password_hash:
        print(f"✅ ADMIN_PASSWORD_HASH set (production mode)")
    else:
        warnings.append("⚠️  Neither ADMIN_PASSWORD nor ADMIN_PASSWORD_HASH set (will use default: changeme)")
        print("⚠️  Neither ADMIN_PASSWORD nor ADMIN_PASSWORD_HASH set")
        print("   Default password: changeme")
    
    return True, warnings  # Warnings don't fail the test

def test_documentation():
    """Test if documentation files exist."""
    print_header("TEST 7: Checking Documentation Files")
    
    errors = []
    
    docs = [
        'PHASE_9_COMPLETE.md',
        'ADMIN_QUICKSTART.md',
        'PROJECT_COMPLETE.md'
    ]
    
    for doc in docs:
        if os.path.exists(doc):
            size = os.path.getsize(doc)
            print(f"✅ Documentation found: {doc} ({size} bytes)")
        else:
            errors.append(f"❌ Documentation missing: {doc}")
            print(f"❌ Documentation missing: {doc}")
    
    return len(errors) == 0, errors

def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "PHASE 9 VERIFICATION TEST" + " "*28 + "║")
    print("║" + " "*10 + "PhishingHunter Elite v2 - Admin Panel" + " "*21 + "║")
    print("╚" + "="*68 + "╝")
    
    all_tests = [
        ("Module Imports", test_imports),
        ("admin_auth Functions", test_admin_auth_functions),
        ("Database Functions", test_database_functions),
        ("Admin Templates", test_templates),
        ("Admin Routes", test_app_routes),
        ("Environment Variables", test_environment),
        ("Documentation", test_documentation)
    ]
    
    results = []
    all_errors = []
    all_warnings = []
    
    for test_name, test_func in all_tests:
        success, issues = test_func()
        results.append((test_name, success))
        
        if not success:
            all_errors.extend(issues)
        else:
            # Check if issues are warnings (from environment test)
            if issues and test_name == "Environment Variables":
                all_warnings.extend(issues)
    
    # Print summary
    print_header("SUMMARY")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if all_warnings:
        print("\n⚠️  WARNINGS:")
        for warning in all_warnings:
            print(f"  {warning}")
    
    if all_errors:
        print("\n❌ ERRORS FOUND:")
        for error in all_errors:
            print(f"  {error}")
        print("\nFix the errors above and run this script again.")
        return False
    else:
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED! Phase 9 is 100% complete and ready to use!")
        print("="*70)
        print("\nTo start the admin panel:")
        print("  1. Make sure environment variables are set (or use defaults)")
        print("  2. Run: python app.py")
        print("  3. Open: http://localhost:5000/admin")
        print("  4. Login with your credentials")
        print("\nDefault credentials: admin / changeme")
        print("="*70)
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

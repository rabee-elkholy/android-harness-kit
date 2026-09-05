"""Real Android/Room upgrade fixture for SDK-equipped CI, not a simulated device."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'agents/scripts'


def main():
    with tempfile.TemporaryDirectory() as name:
        repo = Path(name)
        files = {
            'settings.gradle': "pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\ndependencyResolutionManagement { repositories { google(); mavenCentral() } }\nrootProject.name='HarnessFixture'\ninclude ':app'\n",
            'build.gradle': "plugins { id 'com.android.application' version '8.7.3' apply false }\n",
            'gradle.properties': 'android.useAndroidX=true\norg.gradle.jvmargs=-Xmx2g\n',
            'gradlew': '#!/bin/sh\nexec gradle "$@"\n',
            '.gitignore': '**/build/\n.gradle/\n.agents/\nagents/state/\n',
            'app/build.gradle': '''plugins { id 'com.android.application' }
android {
 namespace 'com.example.fixture'
 compileSdk 35
 defaultConfig {
  applicationId 'com.example.fixture'
  minSdk 23
  targetSdk 35
  versionCode 1
  versionName '1'
  testInstrumentationRunner 'androidx.test.runner.AndroidJUnitRunner'
  javaCompileOptions { annotationProcessorOptions { arguments += ["room.schemaLocation": "$projectDir/schemas".toString()] } }
 }
 sourceSets { androidTest.assets.srcDirs += files("$projectDir/schemas") }
}
dependencies {
 implementation 'androidx.room:room-runtime:2.6.1'
 annotationProcessor 'androidx.room:room-compiler:2.6.1'
 androidTestImplementation 'androidx.room:room-testing:2.6.1'
 androidTestImplementation 'androidx.test:runner:1.5.2'
 androidTestImplementation 'androidx.test.ext:junit:1.1.5'
 testImplementation 'junit:junit:4.13.2'
}
''',
            'app/src/main/AndroidManifest.xml': '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:theme="@android:style/Theme.Material.Light"/></manifest>',
            'app/src/main/java/com/example/fixture/UserRow.java': '''package com.example.fixture;
import androidx.room.Entity;
import androidx.room.PrimaryKey;
@Entity public class UserRow { @PrimaryKey public int id; public String name; }
''',
            'app/src/main/java/com/example/fixture/AppDatabase.java': '''package com.example.fixture;
import androidx.room.Database;
import androidx.room.RoomDatabase;
@Database(entities = {UserRow.class}, version = 1, exportSchema = true)
public abstract class AppDatabase extends RoomDatabase { }
''',
            'app/src/test/java/com/example/fixture/SanityTest.java': 'package com.example.fixture; public class SanityTest { @org.junit.Test public void arithmetic() { org.junit.Assert.assertEquals(4, 2+2); } }',
        }
        for rel, data in files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        env = os.environ.copy()
        env['HARNESS_REPO'] = str(repo)
        def git(*args):
            subprocess.run(['git', *args], cwd=repo, check=True)
        def gradle(task, schema_generation=False):
            command = [sys.executable, str(SCRIPTS / 'run_gradle_task.py'), task]
            first = subprocess.run(command, cwd=repo, env=env)
            if first.returncode and schema_generation:
                # Only a recorded STALE caused by schema export permits this retry.
                check = subprocess.run([sys.executable, "-c", "import sys;sys.path.insert(0,sys.argv[1]);from _gate_results import read_gate_result,gate_artifact_name;sys.exit(0 if (read_gate_result(gate_artifact_name(sys.argv[2])) or {}).get('status') == 'STALE' else 1)", str(SCRIPTS), task], cwd=repo, env=env)
                if check.returncode == 0:
                    subprocess.run(command, cwd=repo, env=env, check=True)
                    return
            first.check_returncode()
        git('init', '-q')
        git('config', 'user.email', 'fixture@example.invalid')
        git('config', 'user.name', 'CI Fixture')
        git('add', '.')
        git('commit', '-qm', 'Room v1 fixture')
        gradle(':app:assembleDebug', schema_generation=True)
        git('add', 'app/schemas')
        git('commit', '-qm', 'Export v1 Room schema')
        entity = repo / 'app/src/main/java/com/example/fixture/UserRow.java'
        entity.write_text(entity.read_text().replace('public String name;', 'public String name; public String note;'))
        db = repo / 'app/src/main/java/com/example/fixture/AppDatabase.java'
        db.write_text('''package com.example.fixture;
import androidx.room.Database;
import androidx.room.RoomDatabase;
import androidx.room.migration.Migration;
import androidx.sqlite.db.SupportSQLiteDatabase;
@Database(entities = {UserRow.class}, version = 2, exportSchema = true)
public abstract class AppDatabase extends RoomDatabase {
 public static final Migration MIGRATION_1_2 = new Migration(1, 2) {
  public void migrate(SupportSQLiteDatabase db) { db.execSQL("ALTER TABLE UserRow ADD COLUMN note TEXT"); }
 };
 public static AppDatabase open(android.content.Context context) {
  return androidx.room.Room.databaseBuilder(context, AppDatabase.class, "app.db").addMigrations(MIGRATION_1_2).build();
 }
}
''')
        test = repo / 'app/src/androidTest/java/com/example/fixture/MigrationTest.java'
        test.parent.mkdir(parents=True)
        test.write_text('''package com.example.fixture;
import org.junit.Rule;
import org.junit.Test;
import androidx.room.testing.MigrationTestHelper;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.sqlite.db.SupportSQLiteDatabase;
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory;
public class MigrationTest {
 @Rule public MigrationTestHelper helper = new MigrationTestHelper(InstrumentationRegistry.getInstrumentation(), AppDatabase.class.getCanonicalName(), new FrameworkSQLiteOpenHelperFactory());
 @Test public void preservesExistingData() throws Exception {
  SupportSQLiteDatabase db = helper.createDatabase("migration", 1);
  db.execSQL("INSERT INTO UserRow(id,name) VALUES(1,'existing')");
  db.close();
  db = helper.runMigrationsAndValidate("migration", 2, true, AppDatabase.MIGRATION_1_2);
  android.database.Cursor cursor = db.query("SELECT name,note FROM UserRow WHERE id=1");
  org.junit.Assert.assertTrue(cursor.moveToFirst());
  org.junit.Assert.assertEquals("existing", cursor.getString(0));
  org.junit.Assert.assertTrue(cursor.isNull(1));
  cursor.close(); db.close();
 }
}
''')
        gradle(':app:assembleDebug', schema_generation=True)
        subprocess.run([sys.executable, str(SCRIPTS / 'run_tests_gate.py')], cwd=repo, env=env, check=True)
        subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0,sys.argv[1]); import room_guard; ok,msg=room_guard.check_room_working_tree(); print(msg); sys.exit(0 if ok else 1)', str(SCRIPTS)], cwd=repo, env=env, check=True)
        gradle(':app:connectedDebugAndroidTest')
        print('Real Android schema migration and preserved-data assertions passed')


if __name__ == '__main__':
    main()

/**
 * WatermelonDB schema migrations.
 *
 * Every change to schema.ts needs a matching step here AND a matching Alembic
 * revision on the backend. The three move together or sync breaks — see the
 * change-log note at the end of Data_Requirements_Database.md.
 *
 * Without a migration, WatermelonDB wipes the local database on a version
 * bump. On this app that means throwing away a farmer's unsynced field work,
 * so an empty `migrations` array is only acceptable while version === 1.
 */

import {schemaMigrations} from '@nozbe/watermelondb/Schema/migrations';

export default schemaMigrations({
  migrations: [
    // Ví dụ cho lần đổi schema tiếp theo:
    //
    // {
    //   toVersion: 2,
    //   steps: [
    //     addColumns({
    //       table: 'supplies',
    //       columns: [{name: 'supplier_name', type: 'string', isOptional: true}],
    //     }),
    //   ],
    // },
  ],
});

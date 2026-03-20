"""US-29, US-30: Collection & Report Jobs 테스트."""

import asyncio

from perpetual_predict.scheduler.jobs import collection_job, report_job
from perpetual_predict.storage.database import Database


async def main():
    db = Database()
    await db.initialize()

    print("=== Collection Job 테스트 ===")
    await collection_job(db)
    print("✅ 데이터 수집 완료\n")

    print("=== Report Job 테스트 ===")
    report_path = await report_job(db, output_dir="reports")
    if report_path:
        print(f"✅ 리포트 생성: {report_path}")
    else:
        print("⚠️ 리포트 생성 실패 (데이터 부족 가능)")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())

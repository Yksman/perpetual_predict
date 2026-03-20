"""US-27, US-28: Scheduler Manager 테스트."""

import asyncio

from perpetual_predict.scheduler.scheduler import SchedulerManager


async def main():
    print("=== Scheduler Manager 테스트 ===")

    scheduler = SchedulerManager()

    counter = {"value": 0}

    async def sample_job():
        counter["value"] += 1
        print(f"  Job 실행: #{counter['value']}")

    # 2초마다 실행되는 작업 등록
    scheduler.add_interval_job(
        func=sample_job, job_id="test_job", seconds=2, name="테스트 작업"
    )

    print("등록된 작업:")
    for job in scheduler.get_jobs():
        print(f"  - {job.id}: {job.name}")

    print("\n스케줄러 시작 (10초간 실행)...")
    await scheduler.start()

    await asyncio.sleep(10)

    await scheduler.stop()
    print(f"\n✅ 스케줄러 종료 (총 {counter['value']}회 실행)")


if __name__ == "__main__":
    asyncio.run(main())

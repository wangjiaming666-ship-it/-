import { Agent } from "@cursor/february/agent";

async function main() {
  const testCwd = process.env.CURSOR_TEST_CWD ?? process.cwd();
  const options: any = {
    model: { id: process.env.CURSOR_MODEL ?? "composer-2" },
    local: { cwd: testCwd },
  };
  if (process.env.CURSOR_API_KEY) {
    options.apiKey = process.env.CURSOR_API_KEY;
  }
  const agent = Agent.create(options);

  try {
    const run = await agent.send('只输出严格 JSON：{"ok": true}');
    for await (const event of run.stream()) {
      console.log(JSON.stringify(event));
    }
    const result = await run.wait();
    console.log("RESULT=" + JSON.stringify(result));
    const runs = await Agent.listRuns(agent.agentId, {
      runtime: "local",
      cwd: process.cwd(),
    });
    console.log("RUNS=" + JSON.stringify(runs));
    const messages = await Agent.messages.list(agent.agentId, {
      runtime: "local",
      cwd: process.cwd(),
    });
    console.log("MESSAGES=" + JSON.stringify(messages));
  } finally {
    agent.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

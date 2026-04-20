import { getCloudRuntimeSummary, listCloudRepositories } from "./cloudApiClient.js";

async function main() {
  const summary = getCloudRuntimeSummary();
  console.log("Cloud runtime summary:");
  console.log(JSON.stringify(summary, null, 2));

  const repositories = await listCloudRepositories();
  console.log("Authorized repositories:");
  console.log(JSON.stringify(repositories, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

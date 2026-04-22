import { logger, type IAgentRuntime, type Project, type ProjectAgent } from '@elizaos/core';
import { character } from './character.ts';
import guthriePlugin from './plugin.ts';

const initCharacter = ({ runtime }: { runtime: IAgentRuntime }) => {
  logger.info('Initializing Guthrie agent');
  logger.info({ name: character.name }, 'Name:');
};

export const guthrieAgent: ProjectAgent = {
  character,
  plugins: [guthriePlugin],
  init: async (runtime: IAgentRuntime) => await initCharacter({ runtime }),
};

const project: Project = {
  agents: [guthrieAgent],
};

export { character } from './character.ts';
export default project;

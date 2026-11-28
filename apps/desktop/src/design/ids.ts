let counter = 0;

/** A new item's (or group's, or branch's) id. */
export const newId = () => `i${Date.now().toString(36)}${(counter++).toString(36)}`;

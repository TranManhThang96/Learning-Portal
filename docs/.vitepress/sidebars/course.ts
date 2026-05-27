import type { DefaultTheme } from "vitepress";

const normalizeCoursePath = (coursePath: string) =>
  `/${coursePath.replace(/^\/+|\/+$/g, "")}`;

export const courseDay = (
  coursePath: string,
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => {
  const dayPath = `${normalizeCoursePath(coursePath)}/${slug}`;

  return {
    text,
    collapsed: true,
    items: [
      { text: "Lesson", link: `${dayPath}/lesson` },
      { text: "Resources", link: `${dayPath}/resources` },
      { text: "Exercises", link: `${dayPath}/exercises` },
    ],
  };
};

export const createCourseDay = (coursePath: string) =>
  (text: string, slug: string) => courseDay(coursePath, text, slug);

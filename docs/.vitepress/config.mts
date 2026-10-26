import process from "node:process";
import { execSync } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitepress";

const __dirname = fileURLToPath(new URL('.', import.meta.url));

const title = "dj-inertiajs";
const description = "A Django-native server-side adapter for Inertia.js";

// https://vitepress.dev/reference/site-config
export default defineConfig({
    base: process.env.BASE_PATH,
    title: title,
    description: description,

    cleanUrls: true,

    head: [
        ["meta", { name: "twitter:description", content: description }],

        ["meta", { property: "og:type", content: "website" }],
        ["meta", { property: "og:locale", content: "en_US" }],
        ["meta", { property: "og:site_name", content: title }],
        ["meta", { property: "og:description", content: description }],
    ],

    vite: {
        plugins: [
            {
                name: 'generate-llm-docs',
                buildStart() {
                    // Regenerate LLM docs before build
                    console.log('Regenerating LLM documentation...')
                    execSync('node scripts/extract-docs.js', {
                        cwd: join(__dirname, '..'),
                    })
                    console.log('LLM documentation updated!')
                },
            },
        ],
    },

    themeConfig: {
        // https://vitepress.dev/reference/default-theme-config
        nav: [
            { text: "Home", link: "/" },
            { text: "Guide", link: "/guide" },
            {
                text: "Links",
                items: [
                    {
                        text: "Official Inertia.js docs",
                        link: "https://inertiajs.com",
                    },
                ],
            },
            { text: "LLMs", link: "/llms-full.txt" },
        ],


        sidebar: {
            "/guide/": [
                {
                    items: [{ text: "Introduction", link: "/guide" }],
                },
                {
                    text: "Installation",
                    items: [
                        {
                            text: "Server-side",
                            link: "/guide/server-side-setup",
                        },
                        {
                            text: "Client-side",
                            link: "/guide/client-side-setup",
                        },
                    ],
                },
                {
                    text: "Upgrading",
                    items: [
                        {
                            text: "From inertia-django",
                            link: "/guide/upgrading-from-inertia-django",
                        },
                    ],
                },
                {
                    text: "Core concepts",
                    items: [
                        { text: "How it works", link: "/guide/how-it-works" },
                        { text: "The protocol", link: "/guide/the-protocol" },
                    ],
                },
                {
                    text: "The basics",
                    items: [
                        { text: "Partial reloads", link: "/guide/partial-reloads" },
                    ],
                },
                {
                    text:
                        'Client side<a class="sidebar-subtitle vp-external-link-icon" href="https://inertiajs.com/docs/v3/getting-started" target="_blank" rel="noreferrer">inertiajs.com</a>',
                    items: [
                        { text: "Links", link: "https://inertiajs.com/docs/v3/the-basics/links" },
                        {
                            text: "Scroll management",
                            link: "https://inertiajs.com/docs/v3/advanced/scroll-management",
                        },
                        {
                            text: "Code splitting",
                            link: "https://inertiajs.com/docs/v3/advanced/code-splitting",
                        },
                    ],
                },
            ],
        },

        socialLinks: [
            {
                icon: "github",
                link: "https://github.com/joshuadavidthomas/inertia-django",
            },
        ],
    },
});

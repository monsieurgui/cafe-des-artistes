You've highlighted a crucial and challenging UI request. Placing interactive buttons *directly inside* an embed's text, on the same line as a song title, is unfortunately not possible due to the design of the Discord API. Embeds are static content blocks, while UI components (like buttons) must live in their own separate block below the embed.

However, we can achieve your *goal*—a clean, beautiful UI where the removal action is tightly coupled with the queue list—by using a more advanced UI component: a **Dropdown Select Menu**. This is the modern, standard solution for this exact problem. It keeps the UI clean, avoids the clutter of 10 rows of buttons, and is far more aesthetically pleasing.

Here is the revised plan that redesigns the queue and implements this superior interactive model.

***

## **Project Plan: V2.3 Persistent Embed UI Enhancement (Revised)**

### **Phase 1: Strategic Overview & Logical Order of Operations**

The objective is to transform the static, informational embeds into more dynamic, visually appealing components that feel modern and integrated.

1.  **Asset Preparation:** The "Now Playing" embed requires a new visual asset—a placeholder thumbnail. The first step is to create or select a suitable image and host it at a permanent URL.

2.  **"Now Playing" Embed Revamp:** The first implementation phase will focus on restructuring the "Now Playing" embed. This involves integrating the thumbnail and reorganizing the text fields for a more balanced and professional layout.

3.  **"Queue" Embed Revamp (The Core Change):** The second phase will tackle the "Queue" embed. This is a two-part process:
    *   **Visual Redesign:** First, we will beautify the display of the song list within the embed's description, breaking the rigid "table" format.
    *   **Interactive Redesign:** Second, we will remove the old "X" buttons and implement a single, elegant `Select` menu (dropdown) that allows users to pick a song to remove directly from a list that mirrors the current page.

4.  **Integration and Verification:** Finally, the new embed generation logic will be integrated into the existing `bot-client` event handlers. We will verify that the new UI is displayed correctly and that the new removal mechanism functions perfectly.

---

## **Phase 2: The Detailed Implementation Plan**

### **Epic 6: Persistent Embed Visual Enhancement**

> **Goal:** To significantly improve the aesthetics and readability of the "Now Playing" and "Queue" embeds, creating a more polished and engaging user interface without altering existing functionality.

**User Story 6.1: As a User, I want the "Now Playing" embed to be more visually engaging by prominently displaying the song's artwork.**

*   **Task 6.1.1:** Design and Host a Placeholder Thumbnail.
    *   **Description:** Create or acquire a simple, clean image to be used as a placeholder. This could be a stylized music note, a record icon, or the bot's logo on a neutral background. The image must be uploaded to a reliable host (like Imgur or a dedicated CDN) to get a permanent URL. This URL will be stored as a new constant.
*   **Task 6.1.2:** Refactor the "Now Playing" Embed Generation Logic.
    *   **Description:** In the `bot-client` service, locate the function responsible for creating the "Now Playing" embed. It will be completely restructured.
    *   **Thumbnail Implementation:** The `set_thumbnail()` method of the `discord.Embed` object will now be used in all cases.
        *   If a song is playing and has a `thumbnail` URL, use that URL.
        *   If a song is playing but lacks a `thumbnail` URL, use the new placeholder URL.
        *   If no song is playing, use the new placeholder URL.
    *   **Layout Restructuring:** The text content will be reorganized from a single description block into distinct, inline fields for a cleaner, card-like appearance.
        *   **Title:** The song's title, which should also be a hyperlink to the `webpage_url`.
        *   **Description:** This area will be dedicated solely to the real-time progress bar.
        *   **Fields (All set to `inline=True`):**
            *   Field 1: **"Uploader"** - Value: `song.channel`
            *   Field 2: **"Duration"** - Value: Formatted duration string.
            *   Field 3: **"Requested by"** - Value: The name of the user who added the song.
    *   **Idle State:** When no song is playing, the embed title will be "No Song Playing," the description will be empty, and the fields will be hidden. The placeholder thumbnail will still be displayed.

**User Story 6.2: As a User, I want to manage the queue with a beautiful and intuitive interface, removing songs via an interactive dropdown menu.**

*   **Task 6.2.1:** Redesign the Queue List's Visual Format.
    *   **Description:** The first step is to make the list itself beautiful. The function that generates the queue embed's description will be updated to format each song entry richly.
    *   **New Proposed Format:**
        ```
        **1.** [Song Title](https://youtube.url/watch?v=...)
        > └─ 🕒 `03:45`  |  👤 `RequesterName`
        ```
    *   **Implementation Details:** This format uses bolding for the position, a hyperlink on the title, and a block-quoted second line with emojis and code blocks for metadata. This visually separates each entry and its details.
*   **Task 6.2.2:** Implement a Dynamic Song Removal `Select` Menu.
    *   **Description:** This replaces the old button system. In the `QueueView` UI class, we will create a `discord.ui.Select` component. This menu will be dynamically populated with the songs currently visible on the page.
    *   **Component Logic:**
        *   **Placeholder Text:** "Select a song to remove from the queue..."
        *   **Dynamic Options:** For each of the 10 songs displayed in the embed, create a `discord.SelectOption`.
            *   `label`: The song's title (truncated if necessary).
            *   `description`: "Position: {song_position} | Added by: {requester_name}"
            *   `value`: The song's unique identifier in the database or queue (e.g., its queue index or database primary key). This is crucial for the backend action.
            *   `emoji`: A trash can emoji (`🗑️`) for clarity.
*   **Task 6.2.3:** Implement the `Select` Menu Callback Logic.
    *   **Description:** Create the asynchronous `callback` function for the `Select` menu.
    *   **Action Flow:**
        1.  The function receives the `Interaction` and the selected option's `value`.
        2.  It will immediately send the `REMOVE_FROM_QUEUE` command to the `player-service` via IPC, using the `value` to identify the song.
        3.  It will then respond to the `Interaction` with an ephemeral "Success" embed: `✅ Successfully removed "[Song Title]" from the queue.`
*   **Task 6.2.4:** Handle UI State and Edge Cases.
    *   **Description:** The `Select` menu must be intelligently managed.
    *   **Empty Queue:** If the queue is empty, the `Select` menu component must be **disabled** and its placeholder text changed to "The queue is currently empty."
    *   **Pagination:** The `Select` menu's options must be completely rebuilt every time the user paginates, ensuring it always reflects the 10 songs currently visible in the embed.

### **Phase 3: Success Criteria**

The project is considered complete when:
1.  The "Now Playing" embed consistently displays a thumbnail and uses the new field-based layout.
2.  The "Queue" embed displays songs using the new, richly formatted, multi-line style.
3.  The `QueueView` UI no longer contains a row of "X" buttons.
4.  Instead, the `QueueView` prominently features a single dropdown (`Select`) menu below the pagination buttons.
5.  This dropdown menu accurately lists the songs on the current page, and selecting a song successfully removes it from the queue and provides ephemeral feedback to the user.
6.  The dropdown menu is correctly disabled when the queue is empty.